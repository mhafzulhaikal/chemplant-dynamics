# engine/simulation_engine.py

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, cast

from engine.appdb import appdb as default_appdb
from engine.case_registry import get_session_factory
from engine.interfaces import SimulationSessionProtocol


class CaseConfig(Protocol):
    """Structural type every case config module must satisfy.

    The engine talks to a case config through this Protocol so it
    can stay case-agnostic: it imports nothing from ``cases.*`` at
    module load time. Every case that wants to use ``SimulationEngine``
    must provide these attributes/functions. The current contract is:

    - ``SIMULATION_PARAMS`` (Mapping[str, Any]): at least ``Ts``,
      ``acceleration``, ``real_time``, ``time_end`` (optional).
    - ``CONTROLLER_MODE`` (Mapping[str, Any]): ``Mode`` key drives
      the controller's default mode; ``LoopModes`` overrides.
    - ``time_unit_short_label(time_unit)`` (callable).
    - ``from_minutes(value, time_unit)`` (callable).
    - ``to_minutes(value, time_unit)`` (callable).
    """

    SIMULATION_PARAMS: MutableMapping[str, Any]
    CONTROLLER_MODE: MutableMapping[str, Any]

    def time_unit_short_label(self, time_unit: str) -> str: ...
    def from_minutes(self, value: float, time_unit: str) -> float: ...
    def to_minutes(self, value: float, time_unit: str) -> float: ...


# Engine is intentionally case-agnostic. The case-specific config
# module and session class are injected via the ``config_module`` and
# ``session_factory`` constructor parameters. Callers that need a
# default STHR behavior should pass them explicitly — the engine
# itself no longer hardcodes any case.
_DEFAULT_CONFIG_MODULE: CaseConfig | None = None
_DEFAULT_SESSION_FACTORY: Callable[[], SimulationSessionProtocol] | None = None


def set_default_case(
    config_module: Any,
    session_factory: Callable[[], SimulationSessionProtocol],
) -> None:
    """Register a default case for callers that don't pass one.

    Used by legacy code paths that historically relied on STHR being
    the implicit default. New code should always pass
    ``config_module`` and ``session_factory`` (or ``case``) explicitly
    to :class:`SimulationEngine`.
    """
    global _DEFAULT_CONFIG_MODULE, _DEFAULT_SESSION_FACTORY
    _DEFAULT_CONFIG_MODULE = config_module
    _DEFAULT_SESSION_FACTORY = session_factory


def _get_case_config(case_name: str) -> Any:
    """Resolve a case's config module by name.

    Imported lazily so this module doesn't pull in any specific case
    at import time. The case registry is the canonical source.
    """
    from gateway.registry.config_registry import get_case_config

    return get_case_config(case_name)


@dataclass(frozen=True)
class SimulationPhase:
    mode: str | None = None
    duration_min: float = 0.0
    duration: float | None = None
    duration_unit: str | None = None
    external_inputs: Mapping[str, float] = field(default_factory=dict)
    input_provider: (
        Callable[
            [int, float, SimulationSessionProtocol],
            Mapping[str, float] | None,
        ]
        | None
    ) = None


class SimulationEngine:
    # Class-level type annotations so static analyzers can verify
    # attribute access on ``self.cfg`` / ``self.appdb`` etc. across
    # the methods. The actual values are set in ``__init__``; the
    # ``__init__`` raises if ``cfg`` could not be resolved, so the
    # post-init value is always a real ``CaseConfig``.
    cfg: CaseConfig
    appdb: Any
    print_fields: set[str] | None
    session_factory: Callable[[], SimulationSessionProtocol]

    def __init__(
        self,
        appdb=default_appdb,
        print_fields: Sequence[str] | None = None,
        session_factory: Callable[[], SimulationSessionProtocol] | None = None,
        case: str | None = None,
        config_module: CaseConfig | None = None,
    ):
        self.appdb = appdb

        # Resolve the case config + session factory in priority order:
        # 1. Explicit ``config_module`` / ``session_factory`` parameters.
        # 2. ``case`` name → use the engine's case registry.
        # 3. Module-level defaults set via :func:`set_default_case`.
        # The engine never imports any specific case's config / session
        # at module load time, so it stays case-agnostic.
        if config_module is None and _DEFAULT_CONFIG_MODULE is not None:
            config_module = _DEFAULT_CONFIG_MODULE
        if config_module is None and case is not None:
            try:
                config_module = _get_case_config(case)
            except Exception:
                config_module = None

        if config_module is None and case is None and session_factory is None:
            raise RuntimeError(
                'SimulationEngine requires either `case`, `config_module`, '
                'or `session_factory`. Engine no longer assumes STHR by '
                'default — pass an explicit case or call '
                '`set_default_case(...)` first.',
            )

        # At this point at least one of `case` / `config_module` /
        # `session_factory` is non-None, so the engine can run. We
        # still allow ``config_module`` to be None in the rare case
        # where someone supplies a session_factory but no config
        # (a degenerate path used by some tests). For day-to-day
        # usage the runtime guarantee is that ``self.cfg`` is set.
        if config_module is not None:
            self.cfg = config_module

        # `print_fields` controls which input/state/output tags are printed.
        # Supported forms: "IN:*", "ST:*", "OUT:*", "IN:TagName", "TagName",
        # etc.
        self.print_fields: set[str] | None = set(print_fields) if print_fields else None

        # session_factory should return a SimulationSessionProtocol instance
        # when called.
        if session_factory is None:
            if case is not None:
                # Use the engine's case registry to look up the session.
                session_factory = get_session_factory(case, self.appdb)
            else:
                session_factory = _DEFAULT_SESSION_FACTORY
                if session_factory is None:
                    raise RuntimeError(
                        'SimulationEngine: no session_factory supplied and no '
                        'default case registered. Pass `case=` or call '
                        '`set_default_case(...)`.',
                    )

        self.session_factory = cast(
            Callable[[], SimulationSessionProtocol],
            session_factory,
        )

    def _time_label(self, time_unit: str) -> str:
        return self.cfg.time_unit_short_label(time_unit)

    def _time_from_minutes(self, value_minutes: float, time_unit: str) -> float:
        return self.cfg.from_minutes(value_minutes, time_unit)

    def _time_to_minutes(self, value: float, time_unit: str) -> float:
        return self.cfg.to_minutes(value, time_unit)

    def _resolve_acceleration(self) -> float:
        acceleration = float(self.cfg.SIMULATION_PARAMS.get('acceleration', 1.0))
        if acceleration <= 0.0:
            raise ValueError("SIMULATION_PARAMS['acceleration'] must be greater than 0.")
        return acceleration

    def _should_run_real_time(self) -> bool:
        return bool(self.cfg.SIMULATION_PARAMS.get('real_time', False))

    def _effective_step_seconds(self, step_seconds: float) -> float:
        if self._should_run_real_time():
            return step_seconds

        # Scale acceleration by Ts so wall-clock sleep time is
        # independent of step size.
        # Example: Ts=1, acl=100: sleep=0.6s; Ts=10, acl=100: sleep=0.6s (not
        # 6s)
        acceleration = self._resolve_acceleration()
        Ts_minutes = float(self.cfg.SIMULATION_PARAMS.get('Ts', 0.01))
        adjusted_acceleration = acceleration * Ts_minutes
        return step_seconds / adjusted_acceleration

    @staticmethod
    def _sample_time_minutes(
        session_time_minutes: float,
        run_clock_start: float | None,
        real_time_mode: bool,
    ) -> float:
        if not real_time_mode or run_clock_start is None:
            return session_time_minutes

        elapsed_minutes = max(0.0, (time.perf_counter() - run_clock_start) / 60.0)
        return elapsed_minutes

    def _pace_step(self, next_tick: float, target_step_seconds: float) -> float:
        now = time.perf_counter()
        sleep_for = next_tick - now
        if sleep_for > 0:
            time.sleep(sleep_for)

        return next_tick + target_step_seconds

    def _build_header(self, input_items, state_items, output_items, time_unit: str) -> str:
        columns = ['real_time', f'time_{self._time_label(time_unit)}', 'mode']
        columns.extend(f'IN:{tag.name}' for _, tag in input_items)
        columns.extend(f'ST:{tag.name}' for _, tag in state_items)
        columns.extend(f'OUT:{tag.name}' for _, tag in output_items)
        return ' | '.join(columns)

    def _filter_items(self, input_items, state_items, output_items):
        # If no filter specified, return items unchanged
        if self.print_fields is None:
            return input_items, state_items, output_items

        pf = self.print_fields

        def include(prefix: str, tagname: str) -> bool:
            return (f'{prefix}:*' in pf) or (f'{prefix}:{tagname}' in pf) or (tagname in pf)

        filtered_inputs = [(k, v) for k, v in input_items if include('IN', v.name)]
        filtered_states = [(k, v) for k, v in state_items if include('ST', v.name)]
        filtered_outputs = [(k, v) for k, v in output_items if include('OUT', v.name)]

        return filtered_inputs, filtered_states, filtered_outputs

    @staticmethod
    def _sync_session_time(session: SimulationSessionProtocol, sim_time: float) -> None:
        session.t = sim_time
        if session.runner is not None:
            session.runner.t = sim_time

    @staticmethod
    def _refresh_session_runtime(session: SimulationSessionProtocol) -> None:
        refresh = getattr(session, 'refresh_runtime_parameters', None)
        if callable(refresh):
            refresh()

    @staticmethod
    def _copy_state_by_position(source_state, target_state):
        source_values = list(source_state)
        target_values = list(target_state)
        limit = min(len(source_values), len(target_values))

        for idx in range(limit):
            target_values[idx] = float(source_values[idx])

        return target_values

    def _transfer_runner_state(self, prev_runner, new_runner, fallback_x0, sim_time: float) -> None:
        if prev_runner is None or new_runner is None:
            return

        prev_state = prev_runner.state()
        new_x0 = (
            list(fallback_x0)
            if fallback_x0 is not None
            else [0.0] * int(getattr(new_runner.sys, 'nstates', 0))
        )

        prev_labels = list(getattr(prev_runner.sys, 'state_labels', None) or [])
        new_labels = list(getattr(new_runner.sys, 'state_labels', None) or [])

        # Ensure new_x0 is large enough to hold all new state labels
        if len(new_x0) < len(new_labels):
            new_x0.extend([0.0] * (len(new_labels) - len(new_x0)))

        if prev_labels and new_labels:
            prev_state_map = {
                prev_labels[idx]: float(prev_state[idx])
                for idx in range(min(len(prev_labels), len(prev_state)))
            }

            matched = False
            for idx, label in enumerate(new_labels):
                if label in prev_state_map:
                    new_x0[idx] = prev_state_map[label]
                    matched = True

            if not matched:
                new_x0 = self._copy_state_by_position(prev_state, new_x0)
        else:
            new_x0 = self._copy_state_by_position(prev_state, new_x0)

        new_runner.reset(x0=new_x0, t0=sim_time)

    @staticmethod
    def _resolve_override_map(
        phase: SimulationPhase,
        step_index: int,
        sim_time: float,
        session: SimulationSessionProtocol,
    ) -> dict[str, float]:
        overrides = dict(phase.external_inputs)
        if phase.input_provider is not None:
            dynamic_overrides = phase.input_provider(step_index, sim_time, session)
            if dynamic_overrides:
                overrides.update(dynamic_overrides)
        return overrides

    def _render_row(
        self,
        session: SimulationSessionProtocol,
        real_time: str,
        sample_time: float,
        time_unit: str,
        mode_name: str | None,
        input_items,
        state_items,
        output_items,
    ) -> str:
        row = [
            real_time,
            f'{self._time_from_minutes(sample_time, time_unit):.3f}',
            mode_name or '',
        ]

        for raw_name, _ in input_items:
            value = session.last_inputs.get(raw_name)
            row.append(f'{float(value):.6f}' if value is not None else '')

        for _, tag in state_items:
            value = session.last_states.get(tag.name)
            row.append(f'{float(value):.6f}' if value is not None else '')

        for _, tag in output_items:
            value = session.last_outputs.get(tag.name)
            row.append(f'{float(value):.6f}' if value is not None else '')

        return ' | '.join(row)

    @staticmethod
    def _emit_event(
        event_sink: Callable[[Mapping[str, object]], None] | None,
        event_type: str,
        **payload: object,
    ) -> None:
        if event_sink is None:
            return
        event: dict[str, object] = {'type': event_type}
        for key, value in payload.items():
            event[key] = value
        event_sink(event)

    @staticmethod
    def _tag_items(session: SimulationSessionProtocol):
        return (
            list(session.input_tags.items()),
            list(session.state_tags.items()),
            list(session.output_tags.items()),
        )

    @staticmethod
    def _flush_timeseries_buffer(session: SimulationSessionProtocol | None) -> None:
        if session is None:
            return

        try:
            flush = getattr(session, 'flush_timeseries_buffer', None)
            if callable(flush):
                flush()
        except Exception:
            pass

    def _phase_step_count(
        self,
        phase: SimulationPhase,
        session: SimulationSessionProtocol,
        schedule_time_unit: str,
    ) -> int:
        phase_value = phase.duration if phase.duration is not None else phase.duration_min
        phase_unit = phase.duration_unit or (
            schedule_time_unit if phase.duration is not None else 'minutes'
        )
        phase_minutes = self._time_to_minutes(phase_value, phase_unit)
        return max(0, int(math.ceil(float(phase_minutes) / float(session.Ts))))

    def run_simulation(
        self,
        steps: int | None = None,
        time_end: float | None = None,
        input_provider: (
            Callable[
                [int, float, SimulationSessionProtocol],
                Mapping[str, float] | None,
            ]
            | None
        ) = None,
        event_sink: (Callable[[Mapping[str, object]], None] | None) = None,
    ) -> None:
        session = self.session_factory()

        if session.runner is None:
            self._emit_event(
                event_sink,
                'status',
                state='idle',
                message=('Controller mode is unrecognized; nothing to simulate.'),
            )
            logging.info('Controller mode is unrecognized; nothing to simulate.')
            return

        raw_time_end = (
            float(self.cfg.SIMULATION_PARAMS.get('time_end', float('inf')))
            if time_end is None
            else float(time_end)
        )
        time_unit = session.time_unit
        time_end_minutes = (
            self._time_to_minutes(raw_time_end, time_unit)
            if math.isfinite(raw_time_end)
            else float('inf')
        )
        has_finite_time_end = math.isfinite(time_end_minutes)

        if steps is None and has_finite_time_end:
            step_limit = None
            run_description = f'time_end={raw_time_end} {self._time_label(time_unit)}'
        elif steps is None:
            step_limit = None
            run_description = f'time_end=infinite {self._time_label(time_unit)}'
        else:
            step_limit = max(0, int(steps))
            run_description = f'steps={step_limit}'

        # reuse the created session for template/tag discovery to avoid
        # constructing a second session which can have side-effects
        template_session = session
        input_items, state_items, output_items = self._tag_items(template_session)

        (
            filt_input_items,
            filt_state_items,
            filt_output_items,
        ) = self._filter_items(input_items, state_items, output_items)

        sample_period_seconds = session.Ts * 60.0
        real_time_mode = self._should_run_real_time()
        run_clock_start = time.perf_counter() if real_time_mode else None
        # initial effective pacing (may be recomputed each loop)
        target_step_seconds = self._effective_step_seconds(sample_period_seconds)
        next_tick = time.perf_counter()

        logging.info(
            'Starting simulation: mode=%s %s ts=%s %s effective_accel=%s',
            session.mode,
            run_description,
            session.Ts,
            self._time_label(time_unit),
            target_step_seconds / sample_period_seconds,
        )
        self._emit_event(
            event_sink,
            'status',
            state='starting',
            message=f'Starting simulation: mode={session.mode} {run_description}',
            mode=session.mode,
            time_unit=time_unit,
            time_end=raw_time_end,
            Ts=session.Ts,
        )
        print(self._build_header(filt_input_items, filt_state_items, filt_output_items, time_unit))

        try:
            step_index = 0
            while True:
                self._refresh_session_runtime(session)
                raw_time_end = float(self.cfg.SIMULATION_PARAMS.get('time_end', raw_time_end))
                time_unit = session.time_unit
                time_end_minutes = (
                    self._time_to_minutes(raw_time_end, time_unit)
                    if math.isfinite(raw_time_end)
                    else float('inf')
                )
                has_finite_time_end = math.isfinite(time_end_minutes)
                real_time_mode = self._should_run_real_time()
                if real_time_mode and run_clock_start is None:
                    run_clock_start = time.perf_counter()

                if step_limit is not None and step_limit == 0:
                    break

                if has_finite_time_end and session.t > time_end_minutes + 1e-12:
                    break

                sample_period_seconds = session.Ts * 60.0
                # recalculate pacing each loop to pick up any runtime changes
                target_step_seconds = self._effective_step_seconds(sample_period_seconds)
                next_tick = self._pace_step(next_tick, target_step_seconds)

                # detect if an external controller mode change occurred and
                # switch session/runner to match the new mode while carrying
                # forward the current simulation state/time. This allows the
                # UI to change `CONTROLLER_MODE` mid-run and have the engine
                # immediately reflect the new behavior.
                try:
                    current_global_mode = str(self.cfg.CONTROLLER_MODE.get('Mode', '')).strip()
                    session_mode = getattr(session, 'mode', None) or ''
                    if (
                        current_global_mode
                        and current_global_mode.strip().lower() != str(session_mode).strip().lower()
                    ):
                        logging.info(
                            'Switching simulation session mode: from=%s to=%s',
                            session_mode,
                            current_global_mode,
                        )
                        self._emit_event(
                            event_sink,
                            'status',
                            state='mode-switch',
                            message=(
                                'Switching simulation session'
                                f' mode: from={session_mode}'
                                f' to={current_global_mode}'
                            ),
                            previous_mode=session_mode,
                            mode=current_global_mode,
                        )
                        prev_session = session
                        # create a new session via the factory
                        # (which should pick
                        # up the current CONTROLLER_MODE) and transfer state
                        try:
                            session = self.session_factory()
                            # transfer runner state and sync logical time
                            try:
                                self._transfer_runner_state(
                                    prev_session.runner,
                                    session.runner,
                                    session.X0,
                                    prev_session.t,
                                )
                            except Exception:
                                pass
                            try:
                                self._sync_session_time(
                                    session, float(getattr(prev_session, 't', 0.0))
                                )
                            except Exception:
                                pass

                            # recompute item lists and filters for printing
                            (
                                input_items,
                                state_items,
                                output_items,
                            ) = self._tag_items(session)
                            (
                                filt_input_items,
                                filt_state_items,
                                filt_output_items,
                            ) = self._filter_items(
                                input_items,
                                state_items,
                                output_items,
                            )
                            # update pacing based on new session Ts
                            sample_period_seconds = session.Ts * 60.0
                            target_step_seconds = self._effective_step_seconds(
                                sample_period_seconds
                            )
                        except Exception:
                            # if switching fails, continue with the previous
                            # session
                            session = prev_session
                            pass
                except Exception:
                    # avoid letting mode-detection errors break the run
                    pass

                sample_time = self._sample_time_minutes(session.t, run_clock_start, real_time_mode)
                self._sync_session_time(session, sample_time)
                real_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                overrides = (
                    input_provider(step_index, sample_time, session)
                    if input_provider is not None
                    else None
                )
                session.step(external_inputs=dict(overrides) if overrides else None)

                self._emit_event(
                    event_sink,
                    'step',
                    index=step_index,
                    time=sample_time,
                    real_time=real_time,
                    mode=session.mode,
                    inputs=dict(getattr(session, 'last_inputs', {})),
                    states=dict(getattr(session, 'last_states', {})),
                    outputs=dict(getattr(session, 'last_outputs', {})),
                )

                print(
                    self._render_row(
                        session,
                        real_time,
                        sample_time,
                        time_unit,
                        session.mode,
                        filt_input_items,
                        filt_state_items,
                        filt_output_items,
                    )
                )

                step_index += 1

                if step_limit is not None:
                    step_limit -= 1
                    if step_limit <= 0:
                        break

                if has_finite_time_end and session.t > time_end_minutes + 1e-12:
                    break
        except KeyboardInterrupt:
            logging.info('Simulation stopped by user.')
            self._emit_event(
                event_sink,
                'status',
                state='stopped',
                message='Simulation stopped by user.',
            )
        finally:
            # ensure session buffer is flushed at the end of simulation
            self._flush_timeseries_buffer(session)

        logging.info('Simulation finished: records=%s', len(self.appdb.timeseries))
        self._emit_event(
            event_sink,
            'status',
            state='complete',
            message=(f'Simulation finished: records={len(self.appdb.timeseries)}'),
            records=len(self.appdb.timeseries),
        )

    def run_phases(
        self,
        phases: Sequence[SimulationPhase],
        event_sink: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        phase_list = list(phases)
        if not phase_list:
            return

        original_mode = self.cfg.CONTROLLER_MODE.get('Mode')
        template_mode = phase_list[0].mode or str(original_mode or 'Off')

        try:
            self.cfg.CONTROLLER_MODE['Mode'] = template_mode
            template_session = self.session_factory()
            input_items, state_items, output_items = self._tag_items(template_session)
            schedule_time_unit = template_session.time_unit

            (
                filt_input_items,
                filt_state_items,
                filt_output_items,
            ) = self._filter_items(input_items, state_items, output_items)

            print(
                self._build_header(
                    filt_input_items,
                    filt_state_items,
                    filt_output_items,
                    schedule_time_unit,
                )
            )

            global_sim_time = 0.0
            prev_session = None
            real_time_mode = self._should_run_real_time()
            run_clock_start = time.perf_counter() if real_time_mode else None

            for phase_index, phase in enumerate(phase_list):
                if phase.mode is not None:
                    self.cfg.CONTROLLER_MODE['Mode'] = phase.mode

                session = self.session_factory()
                target_step_seconds = self._effective_step_seconds(session.Ts * 60.0)

                if prev_session is not None:
                    self._flush_timeseries_buffer(prev_session)
                    try:
                        self._transfer_runner_state(
                            prev_session.runner,
                            session.runner,
                            session.X0,
                            global_sim_time,
                        )
                        self._sync_session_time(session, global_sim_time)
                    except Exception:
                        pass

                phase_value = phase.duration if phase.duration is not None else phase.duration_min
                phase_unit = phase.duration_unit or (
                    schedule_time_unit if phase.duration is not None else 'minutes'
                )
                steps = self._phase_step_count(phase, session, schedule_time_unit)
                logging.info(
                    'Running mode %s for %s %s (%s steps)',
                    session.mode,
                    phase_value,
                    self._time_label(phase_unit),
                    steps,
                )
                self._emit_event(
                    event_sink,
                    'status',
                    state='starting',
                    message=f'Running mode {session.mode} for {phase_value} {
                        self._time_label(phase_unit)
                    } ({steps} steps)',
                    mode=session.mode,
                    phase_duration=phase_value,
                    phase_unit=phase_unit,
                    steps=steps,
                )

                next_tick = time.perf_counter()
                for step_index in range(steps):
                    next_tick = self._pace_step(next_tick, target_step_seconds)

                    sample_time = self._sample_time_minutes(
                        global_sim_time, run_clock_start, real_time_mode
                    )
                    self._sync_session_time(session, sample_time)
                    real_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    overrides = self._resolve_override_map(phase, step_index, sample_time, session)
                    session.step(external_inputs=overrides if overrides else None)

                    self._emit_event(
                        event_sink,
                        'step',
                        index=step_index,
                        time=sample_time,
                        real_time=real_time,
                        mode=session.mode,
                        phase_index=phase_index,
                        inputs=dict(getattr(session, 'last_inputs', {})),
                        states=dict(getattr(session, 'last_states', {})),
                        outputs=dict(getattr(session, 'last_outputs', {})),
                    )

                    print(
                        self._render_row(
                            session,
                            real_time,
                            sample_time,
                            schedule_time_unit,
                            session.mode,
                            filt_input_items,
                            filt_state_items,
                            filt_output_items,
                        )
                    )

                    global_sim_time = float(getattr(session, 't', sample_time + session.Ts))
                prev_session = session
                # flush final session buffer after all phases
                self._flush_timeseries_buffer(prev_session)

                self._emit_event(
                    event_sink,
                    'status',
                    state='phase-complete',
                    message=f'Completed phase {phase_index}',
                    phase_index=phase_index,
                    mode=session.mode,
                )
        finally:
            if original_mode is not None:
                self.cfg.CONTROLLER_MODE['Mode'] = original_mode
