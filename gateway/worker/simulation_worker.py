# gateway/worker/simulation_worker.py

"""Simulation worker thread loop and physics pacing.

SimulationWorker is a deep module that owns the physics step loop and
clock pacing. It accepts only a WorkerContext — it never holds a reference
to BridgeFacade.

Invariants (enforced by the WorkerContext seam):
- No direct BridgeState reads or writes.
- No I/O: no file writes, no console output.
- No appdb or _step_log access.
- No lock acquisitions.
- Every interaction with the outside world goes through ctx or ctx.ipc.
"""

from __future__ import annotations

import logging
import math
import sys
import time

from engine.runtime_config import RuntimeConfig
from engine.simulation_clock import SimulationClock, make_clock
from gateway.worker.worker_context import WorkerContext

logger = logging.getLogger(__name__)


def _set_worker_priority_low() -> None:
    """Lower the current thread's scheduling priority on Windows."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
        kernel32.SetThreadPriority.restype = wintypes.BOOL
        handle = kernel32.GetCurrentThread()
        kernel32.SetThreadPriority(handle, -1)
    except Exception:
        pass


class SimulationWorker:
    """Orchestrates the physics engine step loop and clock pacing.

    Accepts only a :class:`~gateway.worker.worker_context.WorkerContext` — it never
    holds a reference to :class:`~gateway.core.bridge_class.Bridge`.

    The entire interaction surface with BridgeFacade is::

        ctx.read_config()               — runtime params + legacy-cfg sync
        ctx.apply_config(rc)            — push corrected RuntimeConfig
        ctx.pacing_signature(rc)        — detect clock rebuild need
        ctx.read_input_overrides()      — lock-safe override snapshot
        ctx.update_state(**kwargs)      — BridgeState writes
        ctx.set_global_sim_time(t)      — update both private clock + state
        ctx.sync_tick(session, rc)      — per-tick Bridge bookkeeping
        ctx.record_step(i, t, session)  — IPC + step_log + timeseries
        ctx.flush_session()             — session buffer drain
        ctx.persist_profile()           — browser storage write
        ctx.initialize_session(session) — log fields + input seed
        ctx.queue_status(msg, mode)     — status BridgeRecord push
        ctx.ipc                         — BridgeIPC (events, drain)
        ctx.stepper                     — SimulationStepper (physics)
    """

    def __init__(self, ctx: WorkerContext) -> None:
        self.ctx = ctx

    # -------------------------------------------------------------------------
    # Entry point
    # -------------------------------------------------------------------------

    def run(self) -> None:
        """Main entry point for the worker thread.

        Runs ``_worker_loop`` and cleans up regardless of how it exits.
        The worker never nulls ``bridge._worker`` — BridgeFacade detects
        termination via ``thread.is_alive()`` at the next call.
        """
        terminal_status = 'stopped'
        try:
            terminal_status = self._worker_loop()
        except KeyboardInterrupt:
            self.ctx.queue_status('Simulation stopped by user.')
        except Exception as exc:
            logger.exception('Bridge worker failed.')
            self.ctx.queue_status(f'Bridge worker failed: {exc}')
            terminal_status = 'error'
            self.ctx.update_state(status='error')
        finally:
            self.ctx.update_state(
                natural_stop=(terminal_status == 'complete'),
                running=False,
            )
            self.ctx.flush_session()

    # -------------------------------------------------------------------------
    # Clock
    # -------------------------------------------------------------------------

    def _make_clock(self, runtime_config: RuntimeConfig) -> SimulationClock:
        accel = max(float(runtime_config.acceleration or 1.0), 1e-12)
        clock = make_clock(
            real_time=runtime_config.real_time,
            acceleration=accel,
        )
        clock.reset()
        return clock

    # -------------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------------

    def _worker_loop(self) -> str:
        """Run the simulation step loop.

        Returns the terminal status string: ``'complete'``, ``'stopped'``,
        or ``'idle'``.
        """
        ctx = self.ctx
        ipc = ctx.ipc
        stepper = ctx.stepper

        runtime_config = ctx.read_config()

        _set_worker_priority_low()

        # ── Pre-loop: validate session ───────────────────────────────────────
        session = stepper.session
        if getattr(session, 'runner', None) is None:
            ctx.queue_status(
                'Controller mode is unrecognized; nothing to simulate.',
                mode=str(getattr(session, 'mode', None)),
            )
            ctx.update_state(running=False, status='idle')
            return 'idle'

        ctx.initialize_session(session)

        # ── Pre-loop: resume vs fresh start ──────────────────────────────────
        startup = ctx.startup()

        if abs(startup.global_sim_time) < 1e-12:
            stepper.reset(scenario=startup.scenario)
            session = stepper.session
        elif startup.has_history:
            stepper.reset(
                scenario=startup.scenario,
                restore_last_states=startup.last_step_states,
                restore_t=startup.global_sim_time,
            )
            session = stepper.session

        ctx.update_state(
            controller_mode=str(session.mode or runtime_config.controller_mode),
        )

        clock = self._make_clock(runtime_config)
        pacing_signature = ctx.pacing_signature(runtime_config)

        step_index = max(startup.last_step + 1, 0)
        sample_time = startup.global_sim_time

        # ── Pre-loop: tiny time_end guard ────────────────────────────────────
        try:
            parsed_time_end = float(runtime_config.time_end)
            if (
                math.isfinite(parsed_time_end)
                and parsed_time_end <= float(session.Ts) + 1e-12
                and abs(startup.global_sim_time) < 1e-12
            ):
                runtime_config = RuntimeConfig(
                    controller_mode=runtime_config.controller_mode,
                    Ts=runtime_config.Ts,
                    acceleration=runtime_config.acceleration,
                    real_time=runtime_config.real_time,
                    time_end=float('inf'),
                    loop_modes=runtime_config.loop_modes,
                )
                ctx.apply_config(runtime_config)
                ctx.persist_profile()
                ctx.queue_status(
                    'Ignored tiny time_end on startup (treated as no end).',
                    mode=str(session.mode),
                )
                time_end_minutes = float('inf')
            else:
                time_end_minutes = stepper.time_end_to_minutes(runtime_config.time_end)
        except Exception:
            time_end_minutes = stepper.time_end_to_minutes(runtime_config.time_end)

        ctx.queue_status(
            f'Starting simulation: mode={session.mode}, '
            f'real_time={runtime_config.real_time}, '
            f'acceleration={runtime_config.acceleration}, '
            f'time_end={runtime_config.time_end}',
            mode=str(session.mode),
        )

        ctx.update_state(status='running')

        # ── Step loop ────────────────────────────────────────────────────────
        while not ipc.is_stopped():
            # Pause handling
            if ipc.is_paused():
                ctx.update_state(status='paused', running=False)
                while ipc.is_paused() and not ipc.is_stopped():
                    time.sleep(0.1)
                if ipc.is_stopped():
                    break
                ctx.update_state(running=True, status='running')

            runtime_config = ctx.read_config()

            # Clock rebuild check
            new_pacing_signature = ctx.pacing_signature(runtime_config)
            if ipc.config_changed_event.is_set():
                ipc.config_changed_event.clear()
                if new_pacing_signature != pacing_signature:
                    clock = self._make_clock(runtime_config)
                    pacing_signature = new_pacing_signature
                    continue

            ctx.sync_tick(session, runtime_config)
            time_end_minutes = stepper.time_end_to_minutes(runtime_config.time_end)

            # Finish checks (pre-step)
            if stepper.is_finished(sample_time, time_end_minutes):
                ctx.update_state(status='complete')
                return 'complete'

            if stepper.would_overshoot(sample_time, float(session.Ts), time_end_minutes):
                ctx.update_state(status='complete')
                return 'complete'

            # Restart event
            if ipc.restart_event.is_set():
                ipc.restart_event.clear()
                ipc.config_changed_event.clear()

                stepper.rebuild_session()
                session = stepper.session
                runtime_config = ctx.read_config()
                clock = self._make_clock(runtime_config)
                pacing_signature = ctx.pacing_signature(runtime_config)
                continue

            # Mode-mismatch detection
            # After read_config() the legacy cfg is in sync, so
            # runtime_config.controller_mode equals
            # cfg.CONTROLLER_MODE['Mode'].
            current_global_mode = runtime_config.controller_mode.strip()
            session_mode = str(getattr(session, 'mode', '')).strip()

            if current_global_mode and current_global_mode.lower() != session_mode.lower():
                stepper.rebuild_session()
                session = stepper.session
                runtime_config = ctx.read_config()
                clock = self._make_clock(runtime_config)
                pacing_signature = ctx.pacing_signature(runtime_config)

                ctx.queue_status(
                    f'Switching simulation session mode: '
                    f'from={session_mode} to={current_global_mode}',
                    mode=current_global_mode,
                )
                ctx.update_state(controller_mode=current_global_mode)
                continue

            # Clock pacing
            step_due = clock.wait_next_step(
                float(session.Ts),
                should_interrupt=lambda: (
                    ipc.is_stopped()
                    or ipc.restart_event.is_set()
                    or ipc.config_changed_event.is_set()
                ),
            )

            if not step_due:
                continue

            # ── Physics step ─────────────────────────────────────────────────
            overrides = ctx.read_input_overrides()
            stepper.step(overrides, sample_time)

            ctx.update_state(last_sim_time=sample_time, last_step=step_index)
            ctx.record_step(step_index, sample_time, session)

            sample_time += float(session.Ts)
            ctx.set_global_sim_time(sample_time)
            step_index += 1

            # Finish check (post-step)
            if stepper.is_finished(sample_time, time_end_minutes):
                ctx.update_state(status='complete')
                return 'complete'

        # ── Loop exited via stop signal ──────────────────────────────────────
        ctx.queue_status(
            f'Simulation finished: records={ctx.timeseries_count()}',
            mode=str(getattr(session, 'mode', None) or ctx.current_mode()),
        )
        return 'stopped'
