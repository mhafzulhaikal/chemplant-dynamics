# app/hub/reactive_store.py

"""Reactive storage layer for the ChemPlant Dynamics UI.

Every value written via ``__setitem__`` is automatically:

1. Persisted to ``app.storage.user`` under a case-scoped key so the
   value survives a browser-side page reload.
2. Logged as a human-readable Audit Log entry (e.g.
   "User set TIC-100 Setpoint to 160.0 °C") **only** when the write
   originates from user interaction — engine echoes go through
   :meth:`update_from_engine` which suppresses logging.
3. Forwarded to the engine through the provided *push_to_engine*
   callable (injected by :class:`HubStoreAdapter` to avoid a circular
   import with ``signal_hub``).

Design decisions
----------------
* Inherits from ``dict`` so NiceGUI's ``bind_value`` mechanism works
  out-of-the-box (it calls ``__setitem__`` / ``__getitem__``).
* The ``_suppress_log`` flag is thread-safe enough for the NiceGUI
  event-loop context (single-threaded): engine echoes arrive through
  the ui.timer tick which calls ``update_from_engine``; user writes
  arrive through UI event callbacks which call ``__setitem__`` without
  the flag.
* Storage key uses a **flat** format ``hub_snapshot_<case>`` rather
  than the colon-separated ``hub_snapshot:<case>`` used by the legacy
  ``_maybe_persist_snapshot`` so both keys can co-exist during the
  migration without conflict.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel that marks an "unknown" previous value (avoids comparing
# None / 0 when a key is first written).
_MISSING = object()


class ReactiveActionStore(dict):
    """Reactive dict with audit-log interception and persistence.

    Parameters
    ----------
    case_slug:
        The case name used to scope ``app.storage.user`` keys
        (e.g. ``'sthr'``).
    registry:
        A :class:`~app.hub.controller_registry.ControllerRegistry` instance
        for looking up human-readable signal metadata.
    push_to_engine:
        Callable ``(modal_key: str, value: float) -> None`` that forwards
        UI-originated writes to the engine.  Injected by
        :class:`HubStoreAdapter` to avoid a circular import.  When
        ``None``, values are only persisted + logged but not sent to the
        engine (useful in test / standalone contexts).
    bridge:
        The bridge object — passed to ``write_audit_log`` so the logger
        can stamp the sim-time on the entry.
    """

    # Keys that map to human-readable UI-preference labels.
    _UI_PREF_LABELS: dict[str, str] = {
        'rt_toggle_state': 'Real-Time Mode',
        'sim_speed_state': 'Simulation Speed',
        'sim_time_end_state': 'Simulation End Time',
        'scenario_state': 'Scenario',
    }

    def __init__(
        self,
        case_slug: str,
        registry: Any,
        push_to_engine: Callable[[str, float], None] | None = None,
        bridge: Any = None,
    ) -> None:
        super().__init__()
        self.case_slug = case_slug
        self.registry = registry
        self._push_to_engine = push_to_engine
        self.bridge = bridge
        self._suppress_log: bool = False

    # ----------------------------------------------------------------------------------
    # Audit Log
    # ------------------------------------------------------------------

    def _human_label(self, key: str, value: Any) -> str:
        """Return a human-readable audit-log message for the given change."""
        # Controller-registry-backed signal
        spec = self.registry.get_by_modal_key(key)
        if spec:
            # Prefer title > svg_id > derive from engine_tag prefix.
            # Engine tags like 'TSP-100.SP' or 'TC-100.Kc' have the
            # controller name before the dot (e.g. 'TC-100', 'TSP-100').
            # We use the first part of the engine_tag as a fallback so
            # the log reads "User set TC-100 Gain (Kc) to 5.5" rather
            # than the generic "User set kc to 5.5".
            if spec.title:
                tag = spec.title.upper()
            elif spec.svg_id:
                tag = spec.svg_id.upper()
            elif spec.engine_tag and '.' in spec.engine_tag:
                tag = spec.engine_tag.split('.')[0].upper()
            else:
                tag = (spec.engine_tag or spec.modal_key).upper()

            unit = f' {spec.unit}'.rstrip() if spec.unit else ''

            if spec.role == 'sp':
                return f'User set {tag} Setpoint to {value}{unit}'
            if spec.role == 'op':
                return f'User set {tag} Output (OP) to {value}{unit}'
            if spec.role == 'tuning':
                label_map = {
                    'kc': 'Gain (Kc)',
                    'tau_i': 'Integral Time (τI)',
                    'tau_d': 'Derivative Time (τD)',
                }
                param = label_map.get(key, key.upper())
                return f'User set {tag} {param} to {value}{unit}'
            if spec.role == 'status':
                try:
                    mode_val = round(float(value))
                    mode_name = {0: 'OFF', 1: 'MANUAL', 2: 'AUTOMATIC'}.get(mode_val, str(value))
                except (TypeError, ValueError):
                    mode_name = str(value)
                return f'User changed {tag} Mode to {mode_name}'

        # Generic UI-preference keys
        label = self._UI_PREF_LABELS.get(key)
        if label:
            if key == 'rt_toggle_state':
                return f'User turned {label} {"ON" if value else "OFF"}'
            if key == 'sim_speed_state':
                return f'User set {label} to {value}×'
            if key == 'sim_time_end_state':
                try:
                    val_str = 'unlimited' if float(value) == float('inf') else f'{value} min'
                except (TypeError, ValueError):
                    val_str = str(value)
                return f'User set {label} to {val_str}'
            if key == 'scenario_state':
                return f'User selected Scenario: {value}'
            return f'User set {label} to {value}'

        return f'User set {key} to {value}'

    def _write_audit(self, key: str, value: Any) -> None:
        try:
            from app.hub.data_logger import write_audit_log

            msg = self._human_label(key, value)
            write_audit_log(self.case_slug, msg, bridge=self.bridge)
        except Exception:
            logger.debug(
                'ReactiveActionStore: audit log failed for key %r',
                key,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Engine push
    # ------------------------------------------------------------------

    def _push(self, key: str, value: Any) -> None:
        if self._push_to_engine is None:
            return
        try:
            self._push_to_engine(key, float(value))
        except Exception:
            logger.debug(
                'ReactiveActionStore: push_to_engine failed for key %r',
                key,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # dict overrides
    # ------------------------------------------------------------------

    def __setitem__(self, key: str, value: Any) -> None:
        prev = self.get(key, _MISSING)
        # Skip identical values to avoid log spam when NiceGUI's
        # bind_value echoes the current value on reconnect.
        if prev is not _MISSING and prev == value:
            return

        super().__setitem__(key, value)

        if not self._suppress_log:
            # UI-originated write: log + push to engine.
            self._write_audit(key, value)
            self._push(key, value)

    # ------------------------------------------------------------------
    # Engine-driven batch update (no audit log, no engine push)
    # ------------------------------------------------------------------

    def update_from_engine(self, data: dict[str, Any]) -> None:
        """Batch-update from an engine tick without triggering audit logs.

        Called by the ``ModalChild``/``HubStoreAdapter`` once per tick
        so open modal inputs reflect the latest engine state without
        generating spurious log entries.

        Because SignalHub now enforces write-locks, we no longer need to
        artificially ignore writable fields here. The store acts as a
        dumb proxy that blindly accepts the authoritative SignalHub
        snapshot.
        """
        self._suppress_log = True
        try:
            for k, v in data.items():
                prev = self.get(k, _MISSING)
                if prev is _MISSING or prev != v:
                    super().__setitem__(str(k), v)
        finally:
            self._suppress_log = False

    def reset_to_seed(self, seed: dict[str, Any]) -> None:
        """Called after a simulation Reset to clear user overrides.

        Clears all writable keys from the store and repopulates them from
        ``seed`` (the post-reset bridge defaults). This is the one case
        where writable keys must be overwritten from outside — because the
        user clicked Reset and expects the modal to show the case defaults.

        Non-writable keys are updated normally.
        """
        self._suppress_log = True
        try:
            # Clear all keys and replace with the seed.
            self.clear()
            for k, v in seed.items():
                try:
                    super().__setitem__(str(k), v)
                except Exception:
                    pass
        finally:
            self._suppress_log = False
