# app/hub/children/modal_child.py

"""Child that refreshes open controller modals and adapts modal writes.

The existing controller modals (``app/pid/<case>/controller_modal.py``)
expect a store object with a LocalStore-compatible API:

::

    store.get(key, default) -> float
    store.set(key, value)   -> None
    store.all()             -> dict[str, float]

The v2 hub keeps a single canonical snapshot. To plug existing
modals in **without modifying them**, this module exposes
:class:`HubStoreAdapter` — a tiny LocalStore look-alike whose:

- ``get`` reads from the hub snapshot.
- ``set`` calls ``SignalHub.request_write`` (so SP/OP edits route
  via the canonical bidirectional path).
- ``all`` returns a copy of the snapshot.

The :class:`ModalChild` itself just walks the open modals once
per tick and calls their existing ``refresh_modal_values`` —
identical contract to legacy ``BaseLiveFlusher._refresh_open_modals``.

Local **control**:

- ``modal.control.commit(modal_key, value)`` — one-line edit commit
  that delegates to ``hub.request_write``. Used by the v2 page when
  it wires its own buttons (the existing modal classes already use
  ``store.set`` internally, which the adapter routes the same way).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.hub.reactive_store import ReactiveActionStore
from app.hub.signal_hub import SignalHub, TickMeta

logger = logging.getLogger(__name__)


class HubStoreAdapter(ReactiveActionStore):
    """Facade over SignalHub that uses ReactiveActionStore for persistence and
    logging.

    Inherits from :class:`ReactiveActionStore` so NiceGUI ``bind_value``
    targets can attach to it directly.

    Write path (UI-originated):     ``modal.store.set(key, value)``
    → ``ReactiveActionStore.__setitem__``     → persists to
    ``app.storage.user``     → writes human-readable audit-log entry
    → calls ``hub.request_write(key, value)`` (engine push)

    Read path (engine-originated):     ``hub._tick`` calls
    ``adapter.update_from_engine(snapshot)``     →
    ``ReactiveActionStore.update_from_engine``     → batch-updates dict
    silently (no log, no engine push)

    ``get`` falls back to the hub's live snapshot for keys not yet
    seeded into the reactive dict (e.g. on first load before any tick).
    """

    def __init__(self, hub: SignalHub) -> None:
        self._hub = hub
        super().__init__(
            case_slug=hub._case_slug(),
            registry=hub.registry,
            push_to_engine=hub.request_write,
            bridge=hub.bridge,
        )

    def get(self, key: str, default: Any = 0.0) -> Any:
        # Prefer reactive dict (persisted / user-typed value);
        # fall back to the hub's authoritative snapshot.
        if key in self:
            val = float(self[key])
        else:
            try:
                from app.hub.reactive_store import _MISSING

                if default is _MISSING:
                    # Avoid passing _MISSING to _hub.get since it casts to
                    # float
                    snap = self._hub.snapshot()
                    if key not in snap:
                        return default
            except Exception:
                pass

            # If default is _MISSING but we caught an exception or something,
            # fallback to 0.0 for _hub.get to prevent float() crash
            safe_default = default if not str(type(default).__name__) == 'object' else 0.0
            val = self._hub.get(key, safe_default)

        registry = getattr(self._hub, 'registry', None)
        if registry is not None:
            spec = registry.get_by_modal_key(key)
            if spec and hasattr(registry, '_is_flow_spec') and registry._is_flow_spec(spec):
                val *= 3600.0

        return val

    def set(self, key: str, value: float) -> None:
        registry = getattr(self._hub, 'registry', None)
        if registry is not None:
            spec = registry.get_by_modal_key(key)
            if spec and hasattr(registry, '_is_flow_spec') and registry._is_flow_spec(spec):
                value /= 3600.0

        # LocalStore-compatible write path — routes via __setitem__
        # so audit log + persistence + engine push all fire.
        self[key] = value

    def all(self) -> dict[str, float]:
        return dict(self._hub.snapshot())


class _ModalChildControl:
    """Local control surface for modal-side actions."""

    def __init__(self, owner: ModalChild) -> None:
        self._owner = owner

    def commit(self, modal_key: str, value: float) -> None:
        """One-line write commit — same path the modal's
        ``_apply_numeric_value`` already takes via the adapter."""
        self._owner._hub.request_write(modal_key, value)

    def refresh_now(self) -> None:
        """Force-refresh every open modal (used by the page after a reset or
        scenario change to repaint inputs immediately)."""
        self._owner._refresh(force=True)


class ModalChild:
    """Subscriber that refreshes open controller modals each tick."""

    def __init__(
        self,
        hub: SignalHub,
        modals: Mapping[str, Any] | None = None,
    ) -> None:
        self._hub = hub
        # tag_lower / svg_id → modal instance. We deliberately accept
        # the same dict the legacy ``html_element.controller_modals``
        # exposes, so the v2 page can drop the existing modal set in
        # without a rebuild.
        self._modals: dict[str, Any] = dict(modals or {})
        self._control = _ModalChildControl(self)
        self._unsubscribe: Any = None
        self._last_reset_counter: int = 0

    # ---------------------------------------------------------------
    # Public
    # ---------------------------------------------------------------

    @property
    def control(self) -> _ModalChildControl:
        return self._control

    @property
    def modals(self) -> Mapping[str, Any]:
        return self._modals

    def register(self, key: str, modal: Any) -> None:
        """Add a modal to the dispatch table (key is typically the SVG
        controller id, e.g. ``'tic-100'``)."""
        self._modals[key] = modal

    def register_all(self, modals: Mapping[str, Any]) -> None:
        for key, modal in modals.items():
            self.register(key, modal)

    def attach(self) -> None:
        if self._unsubscribe is None:
            self._unsubscribe = self._hub.subscribe(self)
            try:
                from nicegui import ui

                ui.context.client.on_disconnect(self.detach)
            except Exception:
                pass

    def detach(self) -> None:
        unsubscribe = self._unsubscribe
        self._unsubscribe = None
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception:
                pass

    # ---------------------------------------------------------------
    # Subscriber protocol
    # ---------------------------------------------------------------

    def on_tick(
        self,
        delta_keys: frozenset[str],
        snapshot: Mapping[str, float],
        meta: TickMeta,
    ) -> None:
        """Handle incoming engine ticks and synchronize modal stores.

        Propagates delta snapshot data to all registered modals and triggers
        a refresh if the underlying data has changed. Also handles resetting
        modals to seed values upon engine reset.
        """
        # Detect reset: reset_counter changed since last tick.
        suppress_inputs = meta.reset_counter != self._last_reset_counter
        if suppress_inputs:
            self._last_reset_counter = meta.reset_counter
            # On Reset, repopulate every store with the post-reset snapshot.
            # This clears user overrides (SP=160 → back to 150 after Reset)
            # and restores config defaults.
            for _key, modal in self._modals.items():
                store = getattr(modal, 'store', None)
                if store is not None and hasattr(store, 'reset_to_seed'):
                    try:
                        store.reset_to_seed(dict(snapshot))
                    except Exception:
                        pass
            # Force-refresh ALL modals (open or not) with the reset
            # seed values so that when the operator reopens the modal
            # they see the correct initial values.  We must NOT pass
            # suppress_inputs=True here because that would skip the
            # SP/OP/Kc field writes —
            # exactly the opposite of what we want after a reset.
            self._refresh(force=True, suppress_inputs=False)
            return

        # Push engine snapshot into the ReactiveActionStore (silently —
        # no audit log, no re-push to engine) so the persistent dict
        # stays current. This is the "engine-driven read path" that
        # completes the reactive loop.
        # Writable keys (SP/OP/Kc/τI/τD) are intentionally excluded inside
        # ``update_from_engine`` — see ReactiveActionStore for rationale.
        if delta_keys:
            delta_snapshot = {k: v for k, v in snapshot.items() if k in delta_keys}
            for _key, modal in self._modals.items():
                store = getattr(modal, 'store', None)
                if store is not None and hasattr(store, 'update_from_engine'):
                    try:
                        store.update_from_engine(delta_snapshot)
                    except Exception:
                        pass

        # Avoid useless refreshes when no data changed. The faceplate's
        # input mirror lives in :class:`FaceplateChild`; this child
        # only services the modal dialog inputs.
        if not delta_keys:
            return

        self._refresh(force=False, suppress_inputs=False)

    # ---------------------------------------------------------------
    # Internal
    # ---------------------------------------------------------------

    def _refresh(
        self,
        *,
        force: bool = False,
        suppress_inputs: bool = False,
    ) -> None:
        for key, modal in self._modals.items():
            try:
                is_open = bool(getattr(modal, 'dialog_is_open', False))
            except Exception:
                is_open = False
            if not is_open and not force:
                continue

            if suppress_inputs:
                try:
                    modal._suppress_input_push = True
                except Exception:
                    pass

            try:
                refresh = getattr(modal, 'refresh_modal_values', None)
                if callable(refresh):
                    refresh(force_op_refresh=False, force_sp_refresh=False)
            except Exception:
                logger.exception(
                    'ModalChild: refresh_modal_values failed for %s',
                    key,
                )

            if suppress_inputs:
                try:
                    modal._suppress_input_push = False
                except Exception:
                    pass


__all__ = ['HubStoreAdapter', 'ModalChild']
