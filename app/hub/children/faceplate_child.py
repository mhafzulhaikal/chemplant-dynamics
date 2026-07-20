# app/hub/children/faceplate_child.py

"""Child that drives the right-drawer faceplate.

Thin wrapper around the existing :class:`FaceplatePanel`
(``app/components/faceplate.py``) — we deliberately do NOT
re-implement the faceplate UI in v2; we just route the per-tick
refresh through the hub instead of the legacy flusher's
``on_faceplate_refresh`` callback.

Local **control** (does NOT touch the engine or the hub snapshot):

- ``faceplate.control.open_for(tag)`` — open the faceplate on a tag
- ``faceplate.control.close()`` — close the drawer
- ``faceplate.control.set_drawer(drawer)`` — wire the aside element

Bidirectional writes (SP/OP/Kc edits typed into the drawer inputs)
already route via the controller modal's ``_apply_numeric_value``,
which the legacy stack walks back to ``store.set`` → bridge. In v2
that same path lands in :meth:`SignalHub.request_write` because the
:class:`ModalChild` wraps every modal's store in a hub-backed
adapter (see ``modal_child.py``).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.hub.signal_hub import SignalHub, TickMeta

logger = logging.getLogger(__name__)


class _FaceplateChildControl:
    """Local control surface — open/close/wire the faceplate drawer."""

    def __init__(self, panel: Any) -> None:
        self._panel = panel

    def open_for(self, tag: str) -> None:
        try:
            self._panel.open_for(tag)
        except Exception:
            logger.exception('FaceplateChild: open_for(%r) failed', tag)

    def close(self) -> None:
        try:
            self._panel.close()
        except Exception:
            logger.exception('FaceplateChild: close() failed')

    def set_drawer(self, drawer: Any) -> None:
        try:
            self._panel.set_drawer(drawer)
        except Exception:
            logger.exception('FaceplateChild: set_drawer() failed')

    def register_modal(self, modal: Any) -> None:
        try:
            self._panel.register_modal(modal)
        except Exception:
            logger.exception('FaceplateChild: register_modal() failed')


class FaceplateChild:
    """Subscriber that refreshes the faceplate panel on every tick.

    The panel is rendered ONCE by the page; this child only routes the
    per-tick repaint through the hub (so the page no longer needs its
    own faceplate refresh timer).
    """

    def __init__(
        self,
        hub: SignalHub,
        panel: Any,
    ) -> None:
        self._hub = hub
        self._panel = panel
        self._control = _FaceplateChildControl(panel)
        self._unsubscribe: Any = None
        self._last_reset_counter: int = 0

    @property
    def control(self) -> _FaceplateChildControl:
        return self._control

    @property
    def panel(self) -> Any:
        return self._panel

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
        # Honour the one-tick suppress after reset (same protocol as
        # the legacy BaseLiveFlusher → FaceplatePanel hook). The
        # panel itself checks ``_suppress_input_push`` and skips
        # input writes that would clobber the operator's last-typed
        # values.
        if meta.reset_counter != self._last_reset_counter:
            self._last_reset_counter = meta.reset_counter
            try:
                self._panel._suppress_input_push = True
            except Exception:
                pass
            try:
                self._panel.refresh()
            finally:
                try:
                    self._panel._suppress_input_push = False
                except Exception:
                    pass
            return

        # Only repaint when something actually changed; the panel
        # has its own internal accessors that read the modal store
        # (which a ``ModalChild`` keeps in sync with the snapshot).
        if not delta_keys:
            return
        try:
            self._panel.refresh()
        except Exception:
            logger.exception('FaceplateChild: panel.refresh() raised')


__all__ = ['FaceplateChild']
