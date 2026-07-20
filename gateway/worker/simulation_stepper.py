# gateway/worker/simulation_stepper.py

import logging
import math
from typing import Any

from engine.interfaces import SimulationSessionProtocol
from engine.simulation_engine import SimulationEngine

logger = logging.getLogger(__name__)


class SimulationStepper:
    """Pure domain physics layer extracted from the legacy Bridge class.

    Responsible for engine instantiation, mathematical state transitions,
    and handling initial condition injections (scenarios). Completely
    unaware of thread pacing, locks, or IPC queues.
    """

    def __init__(self, appdb: Any, case_name: str, cfg: Any) -> None:
        self.appdb = appdb
        self.case_name = case_name
        self.cfg = cfg
        self._engine = self._build_engine()
        self._session = self._engine.session_factory()

    @property
    def session(self) -> SimulationSessionProtocol:
        return self._session

    @property
    def engine(self) -> SimulationEngine:
        return self._engine

    def _build_engine(self) -> SimulationEngine:
        return SimulationEngine(
            appdb=self.appdb,
            case=self.case_name,
            config_module=self.cfg,
        )

    def _apply_scenario_x0(self, scenario: str) -> None:
        """Overwrite the runner's initial state vector with
        scenario-specific values."""
        try:
            provider = getattr(self.cfg, 'initial_states_for_scenario', None)
            if not callable(provider):
                return

            scenario = str(scenario or 'operational')
            raw_states = provider(scenario)
            if not isinstance(raw_states, dict):
                return

            scenario_states: dict[str, float] = {str(k): float(v) for k, v in raw_states.items()}
            if not scenario_states:
                return

            runner = getattr(self._session, 'runner', None)
            if runner is None:
                return

            state_labels = list(getattr(runner.sys, 'state_labels', []))
            if not state_labels:
                return

            # Build new x0 from scenario, keeping default for any unlisted
            # states
            new_x = list(runner.state())
            for i, label in enumerate(state_labels):
                state_tag_name_fn = getattr(self._session, '_state_tag_name', None)
                raw_tag = state_tag_name_fn(label) if callable(state_tag_name_fn) else label
                tag_name = str(raw_tag)
                if tag_name in scenario_states:
                    new_x[i] = float(scenario_states[tag_name])

            # Use reset instead of direct assignment to ensure internal cache
            # is updated
            runner.reset(x0=new_x, t0=float(getattr(self._session, 't', 0.0)))
            self._session.X0 = list(new_x)

        except Exception:
            logger.exception('Failed to apply scenario x0 to session runner.')

    def _transfer_session_state(
        self,
        previous_session: SimulationSessionProtocol,
        next_session: SimulationSessionProtocol,
    ) -> None:
        try:
            flush = getattr(previous_session, 'flush_timeseries_buffer', None)
            if callable(flush):
                flush()
        except Exception:
            logger.exception('Failed to flush the previous session before reconfiguration.')

        try:
            if previous_session.runner is not None and next_session.runner is not None:
                self._engine._transfer_runner_state(  # noqa: SLF001
                    previous_session.runner,
                    next_session.runner,
                    next_session.X0,
                    float(getattr(previous_session, 't', 0.0)),
                )
        except Exception:
            logger.exception('Failed to transfer runner state during stepper reconfiguration.')

        try:
            self._engine._sync_session_time(  # noqa: SLF001
                next_session,
                float(getattr(previous_session, 't', 0.0)),
            )
        except Exception:
            logger.exception('Failed to sync session time during stepper reconfiguration.')

    def rebuild_session(self) -> None:
        """Creates a new session from the engine and transfers state over."""
        previous_session = self._session
        next_session = self._engine.session_factory()
        self._transfer_session_state(previous_session, next_session)
        self._session = next_session

    def reset(
        self, scenario: str, restore_last_states: dict | None = None, restore_t: float = 0.0
    ) -> None:
        """Fully resets the engine and session.

        Applies scenario initial conditions, OR if `restore_last_states`
        is given, it will load the state vector to resume the simulation
        from that point.
        """
        self._engine = self._build_engine()
        self._session = self._engine.session_factory()

        if restore_last_states and restore_t > 0:
            try:
                runner = getattr(self._session, 'runner', None)
                if runner is not None:
                    state_labels = list(getattr(runner.sys, 'state_labels', []))
                    if state_labels:
                        new_x = list(runner.state())
                        tag_fn = getattr(self._session, '_state_tag_name', None)
                        for i, label in enumerate(state_labels):
                            tag = tag_fn(label) if callable(tag_fn) else label
                            tag_name = str(tag)
                            if tag_name in restore_last_states:
                                new_x[i] = float(restore_last_states[tag_name])
                        runner.reset(x0=new_x, t0=float(restore_t))
                        self._session.X0 = list(new_x)
            except Exception:
                logger.exception('Failed to restore runner state on continue.')
        else:
            self._apply_scenario_x0(scenario)

    def step(self, overrides: dict[str, float], sample_time: float) -> dict[str, Any]:
        """Perform one discrete step of domain physics.

        Returns a pure dictionary of `inputs`, `states`, `outputs`, and `mode`.
        It does not construct BridgeRecords, sleep, or enqueue to thread IPC.
        """
        self._engine._sync_session_time(self._session, sample_time)  # noqa: SLF001
        self._session.step(external_inputs=overrides if overrides else None)

        last_inputs = getattr(self._session, 'last_inputs', None) or {}
        last_states = getattr(self._session, 'last_states', None) or {}
        last_outputs = getattr(self._session, 'last_outputs', None) or {}

        return {
            # raw reference — copy deferred to record_step()
            'inputs': last_inputs,
            # raw reference — copy deferred to record_step()
            'states': last_states,
            # raw reference — copy deferred to record_step()
            'outputs': last_outputs,
            'mode': str(self._session.mode),
        }

    # -------------------------------------------------------------------------
    # Finish / overshoot guards  (used by SimulationWorker via WorkerContext)
    # -------------------------------------------------------------------------

    def is_finished(self, sim_time: float, time_end_minutes: float) -> bool:
        """Return True when ``sim_time`` has reached the configured end."""
        return sim_time >= time_end_minutes - 1e-12

    def would_overshoot(
        self,
        sim_time: float,
        step: float,
        time_end_minutes: float,
    ) -> bool:
        """Return True when the next step would advance past
        ``time_end_minutes``.

        ``time_end_minutes = inf`` short-circuits to False so an unbounded
        simulation runs forever as expected.
        """
        if not math.isfinite(time_end_minutes):
            return False
        return (sim_time + float(step)) > (time_end_minutes + 1e-12)

    def time_end_to_minutes(self, raw_time_end: float) -> float:
        """Resolve ``raw_time_end`` to minutes.

        ``state.time_end`` is always stored internally in minutes, so no
        unit conversion is required — just propagate inf and return the value.
        """
        if not math.isfinite(raw_time_end):
            return float('inf')
        return float(raw_time_end)
