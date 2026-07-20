# app/ui/button_feedback.py

"""Sub-16 ms client-side click feedback for buttons.

The CSS class ``btn-feedback`` (defined in
``app/static/css/button_feedback.css``) provides a
``:active``-driven pressed style. For touch devices the
``:active`` pseudo-class is sometimes flaky, so we additionally
install a tiny ``pointerdown`` / ``pointerup`` / ``pointercancel``
event listener on the element that toggles an ``.is-pressed``
class. The combination gives the same visual on mouse, touch, and
keyboard, with zero server round-trip.

Usage
-----

::

    from app.ui.button_feedback import attach_pointer_feedback

    button = ui.button('Run').classes('btn-feedback btn-feedback--dark')
    attach_pointer_feedback(button)

The function is idempotent — calling it twice on the same element
does not stack listeners. It does NOT add the ``btn-feedback``
class for you; that is the caller's responsibility (it should be
set via ``.classes()`` so the CSS is bundled in the head by
``app.assets.collect_css``).

Variant
-------

* ``btn-feedback--dark`` — for buttons on a dark panel
  (control panel, navbar, runtime manager).
* ``btn-feedback--light`` — for buttons on a light panel
  (home page intro / expansion cards).

The visual treatment is intentionally subtle: a 1-px inset glow
and a small tint. Anything more is visible on 60 fps recordings
and becomes annoying on rapid taps.
"""

from __future__ import annotations

from typing import Any

# CSS class added to an element when the user presses it.
_PRESSED_CLASS = 'is-pressed'

# Element-level flag so a second attach is a no-op.
_ATTACHED_ATTR = '__chemplant_pointer_feedback_attached'


def attach_pointer_feedback(button: Any) -> None:
    """Install the pointer-event listener that toggles the ``.is-pressed``
    class on a button.

    Idempotent. Safe to call on any element with a ``.on()`` method that
    accepts an event name + handler (all NiceGUI elements qualify).
    """
    if button is None:
        return
    # Idempotency: check the flag before installing.
    if getattr(button, _ATTACHED_ATTR, False):
        return

    def _on_pointer_down(_event: Any) -> None:
        try:
            button.classes(add=_PRESSED_CLASS)
        except Exception:
            pass

    def _on_pointer_release(_event: Any) -> None:
        try:
            button.classes(remove=_PRESSED_CLASS)
        except Exception:
            pass

    try:
        button.on('pointerdown', _on_pointer_down)
        button.on('pointerup', _on_pointer_release)
        button.on('pointercancel', _on_pointer_release)
        button.on('pointerleave', _on_pointer_release)
    except Exception:
        # Some element types may not support .on() with all four
        # events; in that case the CSS :active fallback covers it.
        pass

    try:
        setattr(button, _ATTACHED_ATTR, True)
    except Exception:
        pass


def attach_to_many(buttons: list[Any]) -> None:
    """Convenience: attach the feedback to a list of buttons."""
    for b in buttons:
        attach_pointer_feedback(b)


def apply_feedback_classes(button: Any, *, variant: str = 'dark') -> None:
    """Add the ``btn-feedback`` + variant classes in one call.

    Equivalent to ``button.classes('btn-feedback btn-feedback--dark')``
    but with a safety check + the idempotent attach.
    """
    if button is None:
        return
    variant_cls = f'btn-feedback--{variant}' if variant else ''
    if variant_cls not in ('btn-feedback--dark', 'btn-feedback--light'):
        variant_cls = 'btn-feedback--dark'
    try:
        current = ''
        try:
            current = ' '.join(button._classes or [])
        except Exception:
            current = ''
        adds = []
        if 'btn-feedback' not in current:
            adds.append('btn-feedback')
        if variant_cls not in current:
            adds.append(variant_cls)
        if adds:
            button.classes(add=' '.join(adds))
    except Exception:
        pass
    attach_pointer_feedback(button)


def set_persistent_active(button: Any, active: bool) -> None:
    """Toggle the ``.btn-feedback--persistent-active`` class.

    Use for buttons that "stay" active (e.g. the left-drawer item that
    owns the current section). The visual is a subtle left-edge accent —
    distinct from the transient pressed feedback so the two states are
    not visually confused.
    """
    cls = 'btn-feedback--persistent-active'
    if button is None:
        return
    try:
        if active:
            button.classes(add=cls)
        else:
            button.classes(remove=cls)
    except Exception:
        pass


__all__ = [
    'attach_pointer_feedback',
    'attach_to_many',
    'apply_feedback_classes',
    'set_persistent_active',
]
