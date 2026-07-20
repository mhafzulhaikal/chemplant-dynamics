# app/hub/input_focus_tracker.py

"""Focus tracking for NiceGUI numeric inputs.

NiceGUI's ``ui.number`` does NOT expose a ``is_focused`` attribute
(verified against NiceGUI 3.12.1: ``[a for a in dir(ui.number) if
'focus' in a.lower()] == []``). Without an explicit tracker, the
per-tick refresh from ``ModalChild`` / ``FaceplatePanel`` clobbers
the operator's in-progress SP/OP edits.

This helper closes the gap with a tiny, explicit focus tracker:

- ``attach_focus_tracker(field)`` wires the DOM ``focus`` / ``blur``
  events on the field to flip a transient ``_user_is_editing``
  boolean attribute on the field itself. Idempotent.
- ``is_user_editing(field)`` reads that flag — returns ``False`` if
  the field was never tracked, so refreshes still work for any
  numeric input that didn't opt in.

Used by:

- ``ControllerModal._set_field_value`` in
  ``app/hub/children/modals/base.py`` (per-tick refresh from
  :class:`ModalChild`).
- ``FaceplatePanel._sync_input_from_store`` in
  ``app/components/faceplate.py`` (the drawer's per-tick input mirror).

Runtime Manager numeric inputs (Ts / acceleration / end_time) are
NOT touched by any per-tick refresh — they commit on blur/Enter
only — so they don't need this guard.

Moved here from the legacy ``app/pid/_shared/input_focus_tracker.py``
during the v1 purge — same code, new location.
"""

from __future__ import annotations

from typing import Any

_FLAG_ATTR = '_user_is_editing'
_ATTACHED_ATTR = '_focus_tracker_attached'


def attach_focus_tracker(field: Any) -> None:
    """Wire ``focus`` / ``blur`` on ``field`` to flip the editing flag.

    Idempotent — calling twice on the same field is a no-op so callers
    don't have to track which fields they've already wired. Safe to call
    on objects that don't support ``.on(event, fn)``; a failure there
    leaves the field in its initial (not editing) state.
    """
    if field is None:
        return
    if getattr(field, _ATTACHED_ATTR, False):
        return

    # Initialise the flag before wiring so a refresh that fires
    # between attach and the first focus event still gets the
    # correct (not-editing) answer.
    setattr(field, _FLAG_ATTR, False)

    def _on_focus(_event: Any = None, target: Any = field) -> None:
        try:
            setattr(target, _FLAG_ATTR, True)
        except Exception:
            pass

    def _on_blur(_event: Any = None, target: Any = field) -> None:
        try:
            setattr(target, _FLAG_ATTR, False)
        except Exception:
            pass

    try:
        field.on('focus', _on_focus)
        field.on('blur', _on_blur)
    except Exception:
        # Field type that doesn't support .on(...) — leave the
        # flag at False so refreshes keep working.
        return

    setattr(field, _ATTACHED_ATTR, True)


def is_user_editing(field: Any) -> bool:
    """Return ``True`` if the user is currently focused inside ``field``.

    Always ``False`` for fields that were never tracked.
    """
    if field is None:
        return False
    return bool(getattr(field, _FLAG_ATTR, False))


__all__ = ['attach_focus_tracker', 'is_user_editing']
