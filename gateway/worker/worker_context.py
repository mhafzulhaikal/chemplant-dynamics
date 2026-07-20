# gateway/worker/worker_context.py

"""Narrow seam between BridgeFacade and SimulationWorker.

BridgeFacade builds a WorkerContext before spawning the worker thread.
SimulationWorker accepts only WorkerContext — it never holds a direct
reference to BridgeFacade.

The interface is the test surface: replace WorkerContext with a fake
(subclass or mock) and SimulationWorker becomes testable without NiceGUI,
appdb, or any running simulation infrastructure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from engine.interfaces import SimulationSessionProtocol
from engine.runtime_config import RuntimeConfig
from gateway.core.bridge_ipc import BridgeIPC
from gateway.core.bridge_support import BridgeRecord
from gateway.worker.simulation_stepper import SimulationStepper

if TYPE_CHECKING:
    from gateway.core.bridge_class import Bridge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerStartup:
    """Snapshot of Bridge state read once at the start of the worker loop.

    Collected atomically before the worker thread begins stepping so the
    worker never needs to reach back into Bridge for startup decisions.
    """

    global_sim_time: float
    """Last known simulation clock position in minutes."""

    last_step: int
    """Index of the last completed step (-1 if fresh)."""

    has_history: bool
    """True when ``_step_log`` is non-empty (worker can resume)."""

    last_step_states: dict[str, float]
    """State vector from the final ``_step_log`` entry, used to restore
    the runner when resuming a mid-simulation reconnect."""

    scenario: str
    """Active scenario key (e.g. ``'operational'``, ``'startup'``)."""


class WorkerContext:
    """Narrow interface the SimulationWorker uses to interact with Bridge.

    All public methods delegate to BridgeFacade internals; the ``_bridge``
    reference is private and is never exposed to SimulationWorker.

    Design rules:
    - Every method is a named action with clear semantics.
    - No raw Bridge state is returned; callers receive plain Python values.
    - ``ipc`` and ``stepper`` are exposed directly because they are already
      deep modules with their own clean seams.
    """

    def __init__(self, bridge: Bridge, ipc: BridgeIPC) -> None:
        self._bridge = bridge
        # Public: BridgeIPC and SimulationStepper are clean deep modules.
        self.ipc: BridgeIPC = ipc
        self.stepper: SimulationStepper = bridge._stepper  # noqa: SLF001
        # 3B: Cached timestamp — reformat only when wall-clock second changes.
        self._last_ts_second: int = -1
        self._last_ts_str: str = ''

    # -------------------------------------------------------------------------
    # Startup snapshot
    # -------------------------------------------------------------------------

    def startup(self) -> WorkerStartup:
        """Read startup state from Bridge in one call.

        Called once at the very start of ``_worker_loop`` before the step
        loop begins. The bridge is not running at this point, so no lock is
        needed.
        """
        b = self._bridge
        step_log = b._step_log  # noqa: SLF001
        last_entry: dict | None = step_log[-1] if step_log else None
        return WorkerStartup(
            global_sim_time=float(b._global_sim_time),  # noqa: SLF001
            last_step=int(getattr(b.state, 'last_step', -1)),
            has_history=bool(step_log),
            last_step_states=dict(last_entry.get('states', {}) if last_entry else {}),
            scenario=str(b.state.scenario or 'operational'),
        )

    # -------------------------------------------------------------------------
    # Config
    # -------------------------------------------------------------------------

    def read_config(self) -> RuntimeConfig:
        """Read the current RuntimeConfig from BridgeState and apply it to
        the legacy cfg dict in one atomic operation.

        The worker always calls ``read_config()`` instead of separate
        ``_read_runtime_config`` + ``_apply_runtime_config_to_legacy_cfg``
        calls. The legacy-cfg sync is an implementation detail of Bridge.
        """
        b = self._bridge
        rc = b._read_runtime_config()  # noqa: SLF001
        b._apply_runtime_config_to_legacy_cfg(rc)  # noqa: SLF001
        return rc

    def apply_config(self, runtime_config: RuntimeConfig) -> None:
        """Apply a pre-built RuntimeConfig to the legacy cfg dict.

        Used when the worker constructs a corrected RuntimeConfig locally
        (e.g. tiny time_end → inf) and needs to push it to the legacy dict
        without re-reading from BridgeState.
        """
        self._bridge._apply_runtime_config_to_legacy_cfg(runtime_config)  # noqa: SLF001

    def pacing_signature(self, rc: RuntimeConfig) -> tuple[str, float]:
        """Return the pacing signature for ``rc``.

        Two configs with the same signature do not require a clock rebuild.
        """
        return self._bridge._pacing_signature(rc)  # noqa: SLF001

    # -------------------------------------------------------------------------
    # State reads
    # -------------------------------------------------------------------------

    def read_input_overrides(self) -> dict[str, float]:
        """Return a lock-safe snapshot of the current input overrides."""
        with self._bridge._lock:  # noqa: SLF001
            return dict(self._bridge.state.input_overrides)

    def current_mode(self) -> str:
        """Return the current controller mode string from BridgeState."""
        return str(self._bridge.state.controller_mode or 'Automatic')

    def timeseries_count(self) -> int:
        """Return the current number of records in the appdb timeseries."""
        return len(self._bridge.appdb.timeseries)

    # -------------------------------------------------------------------------
    # State writes
    # -------------------------------------------------------------------------

    def update_state(self, **kwargs: Any) -> None:
        """Write one or more attributes to BridgeState.

        Example::

            ctx.update_state(status='running', running=True)

        Allowed keys mirror the fields of ``BridgeState``. Unknown keys are
        silently ignored so future BridgeState additions do not break the
        worker.
        """
        for key, value in kwargs.items():
            try:
                setattr(self._bridge.state, key, value)
            except Exception:
                logger.exception('WorkerContext.update_state: failed to set %s', key)

    def set_global_sim_time(self, t: float) -> None:
        """Update the Bridge private clock and the bindable BridgeState."""
        self._bridge._global_sim_time = t  # noqa: SLF001
        self._bridge.state.global_sim_time = t

    def sync_tick(
        self,
        session: SimulationSessionProtocol,
        runtime_config: RuntimeConfig,
    ) -> None:
        """Run the per-tick Bridge state sync.

        Calls ``_refresh_session_runtime_parameters`` (session hook) and
        ``_sync_state_from_session_and_config`` (writes Ts, acceleration,
        real_time, time_end, controller_mode to BridgeState from the live
        session and RuntimeConfig).
        """
        b = self._bridge
        b._refresh_session_runtime_parameters(session)  # noqa: SLF001
        b._sync_state_from_session_and_config(session, runtime_config)  # noqa: SLF001

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def record_step(
        self,
        step_index: int,
        sample_time: float,
        session: SimulationSessionProtocol,
    ) -> None:
        """Record one completed physics step.

        Three responsibilities combined in one call so the worker performs
        no persistence logic itself:

        1. Build a ``BridgeRecord`` and push it to the IPC queues.
        2. Append a lightweight entry to ``Bridge._step_log`` (used to
           restore state when a new browser tab connects mid-simulation).
        3. Append full step data to ``appdb.timeseries`` (headless / CSV).
        """
        b = self._bridge
        selected = b.state.selected_log_fields
        inputs = dict(session.last_inputs or {})
        states = dict(session.last_states or {})
        outputs = dict(session.last_outputs or {})

        # 1. IPC record
        # 3B: Cache the formatted timestamp; reformat only when the wall-clock
        # second changes to avoid expensive strftime on every high-rate step.
        _now = datetime.now()
        _now_second = _now.second + _now.minute * 60 + _now.hour * 3600
        if _now_second != self._last_ts_second:
            self._last_ts_str = _now.strftime('%Y-%m-%d %H:%M:%S')
            self._last_ts_second = _now_second

        # Cache selected fields to avoid allocating a new list every step
        if not hasattr(self, '_last_selected_ref') or self._last_selected_ref is not selected:
            self._last_selected_ref = selected
            self._cached_selected = list(selected or [])

        record = BridgeRecord(
            kind='step',
            message='',
            real_time=self._last_ts_str,
            step_index=step_index,
            time_min=sample_time,
            inputs=inputs,
            states=states,
            outputs=outputs,
            mode=str(session.mode),
            selected_fields=self._cached_selected,
        )
        self.ipc.put_record(record)

        # 2. Step log (resume state) - deque automatically bounds to maxlen=9000
        step_log = b._step_log  # noqa: SLF001
        step_log.append(
            {
                'step': step_index,
                'time_min': sample_time,
                'states': states,
            }
        )

        # 3. Timeseries mirror
        b.appdb.timeseries.append(
            {
                'step': step_index,
                'time_min': sample_time,
                'inputs': inputs,
                'states': states,
                'outputs': outputs,
            }
        )

    def flush_session(self) -> None:
        """Flush the active session's timeseries buffer, if it has one."""
        try:
            flush = getattr(self._bridge._session, 'flush_timeseries_buffer', None)  # noqa: SLF001
            if callable(flush):
                flush()
        except Exception:
            logger.exception('WorkerContext.flush_session failed.')

    def persist_profile(self) -> None:
        """Persist the current Bridge profile to the browser storage dict."""
        self._bridge.persist_profile()

    # -------------------------------------------------------------------------
    # Session initialisation
    # -------------------------------------------------------------------------

    def initialize_session(self, session: SimulationSessionProtocol) -> None:
        """Store available log fields and seed input overrides for ``session``.

        Called once at the start of the worker loop after the session is
        confirmed to have a runner.
        """
        b = self._bridge
        b._store_available_log_fields(session)  # noqa: SLF001
        b._seed_input_overrides()  # noqa: SLF001

    # -------------------------------------------------------------------------
    # Status messages
    # -------------------------------------------------------------------------

    def queue_status(self, message: str, mode: str | None = None) -> None:
        """Push a status ``BridgeRecord`` to the IPC queues."""
        effective_mode = mode if mode is not None else self.current_mode()
        record = BridgeRecord(
            kind='status',
            message=message,
            mode=effective_mode,
        )
        self.ipc.put_record(record)

    def update_health(self, health) -> None:
        """Store simulation health metrics on the bridge state."""
        self._bridge.state.health = health
