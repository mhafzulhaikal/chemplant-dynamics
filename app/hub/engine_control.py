# app/hub/engine_control.py

"""Direct, one-line control surface for the engine bridge.

User requirement:

> jika control (run, stop, reset dan lain-lain) yang berhubungan
> dengan control engine langsung 1 line ke engine.

So this module deliberately keeps every public method a thin
passthrough to the bridge. Pages and the navbar do NOT reach into
``bridge.state`` directly — they call ``hub.engine_control.run()``
(etc.) so the wiring stays auditable.

The companion bidirectional path — writing a SP / OP / Kc from a
modal — does NOT live here. That goes through
``SignalHub.request_write(modal_key, value)`` because such writes
are *child → parent → engine* (the engine echoes the value back as
the next step record, which the hub fans out to every child in the
same tick). See ``signal_hub.py``.
"""

from __future__ import annotations

from typing import Any


class EngineControl:
    """Direct one-line surface for engine-lifecycle control.

    All methods are intentionally a single effective call into the
    bridge — no extra orchestration, no notify, no broadcast. They are
    safe to call from any thread that the bridge accepts (the bridge
    serialises its own state writes under ``self._lock``).
    """

    __slots__ = ('_bridge',)

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    # ---------------------------------------------------------------
    # Lifecycle — one line each
    # ---------------------------------------------------------------

    def run(self) -> None:
        """Start (or resume) the simulation worker."""
        self._bridge.start()

    def stop(self) -> None:
        """Pause the simulation worker (resumable via :meth:`run`)."""
        self._bridge.pause()

    def reset(self) -> None:
        """Reset the simulation to its initial state (clears history)."""
        self._bridge.reset()

    # ---------------------------------------------------------------
    # Global runtime config — one line each
    # ---------------------------------------------------------------

    def set_real_time(self, on: bool) -> None:
        """Toggle real-time pacing (acceleration is ignored when on)."""
        self._bridge.state.real_time = bool(on)
        self._bridge.apply_runtime_configuration(restart_if_needed=False)

    def set_acceleration(self, factor: float) -> None:
        """Set simulation acceleration (>1 faster, <1 slower)."""
        self._bridge.state.acceleration = float(factor)
        self._bridge.apply_runtime_configuration(restart_if_needed=False)

    def set_mode(self, mode: str) -> None:
        """Set the global controller mode (Off/Manual/Automatic).

        This is the one method that may rebuild the simulation session —
        the worker picks up the new mode and rebuilds if required. Use
        :meth:`SignalHub.request_write` for per-controller status
        changes (they route through the same path).
        """
        self._bridge.state.controller_mode = str(mode)
        self._bridge.apply_runtime_configuration(restart_if_needed=True)

    def set_time_end(self, value: Any) -> None:
        """Set the simulation end time (UI passes raw input)."""
        self._bridge.set_time_end_from_ui(value)

    def set_scenario(self, scenario: str) -> None:
        """Switch the active scenario (operational / startup / shutdown)."""
        self._bridge.state.scenario = str(scenario)
        self._bridge.apply_runtime_configuration(restart_if_needed=True)

    # ---------------------------------------------------------------
    # Read-only state accessors — also one line each
    # ---------------------------------------------------------------

    @property
    def status(self) -> str:
        return str(self._bridge.state.status or '')

    @property
    def sim_time(self) -> float:
        return float(self._bridge.state.global_sim_time or 0.0)

    @property
    def controller_mode(self) -> str:
        return str(self._bridge.state.controller_mode or '')

    @property
    def real_time(self) -> bool:
        return bool(self._bridge.state.real_time)

    @property
    def bridge(self) -> Any:
        """Escape hatch — exposes the underlying bridge for advanced wiring
        (e.g. the legacy data logger that still consumes ``bridge._step_log``
        directly).

        Children should NOT use this; they go through
        :class:`SignalHub`.
        """
        return self._bridge


__all__ = ['EngineControl']
