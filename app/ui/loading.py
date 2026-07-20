# app/ui/loading.py

"""Full-panel spinner overlay with blurred background.

The overlay is removed instantly when real content mounts — no fade,
no slide, no layout shift.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui


def render_spinner_overlay(*, _label: str = '') -> Any:
    """Render a full-panel spinner overlay.

    The overlay fills its nearest positioned ancestor with a light
    blur. Pointer-events pass through so content behind stays
    interactive, but the blur signals "loading" to the user.
    """
    overlay = ui.element('div').classes('app-spinner-overlay')
    with overlay:
        with ui.element('div').classes('app-spinner-center'):
            # Pure-CSS gradient spinner — no Quasar icon needed.
            ui.element('div').classes('app-spinner-gradient')
    return overlay


def replace_with_real(overlay: Any) -> None:
    """Remove the spinner overlay immediately."""
    if overlay is None:
        return
    _safe_delete(overlay)


def _safe_delete(element: Any) -> None:
    """Remove an element from its parent if still present."""
    try:
        if hasattr(element, 'delete'):
            element.delete()
        else:
            parent_slot = getattr(element, 'parent_slot', None)
            if parent_slot is not None and hasattr(parent_slot.parent, 'remove'):
                parent_slot.parent.remove(element)
    except Exception:
        pass


def _get_dom_id(element: Any) -> str:
    """Best-effort DOM id lookup for a NiceGUI element."""
    try:
        return str(element.id or '')
    except Exception:
        return ''


# Backwards-compatible skeleton aliases — they now return the
# spinner overlay instead of skeleton blocks.


def render_skeleton(*, height_px: int = 200, width: str = '100%') -> Any:
    _ = height_px, width
    return render_spinner_overlay()


def render_skeleton_row() -> Any:
    return render_spinner_overlay()


def render_skeleton_card() -> Any:
    return render_spinner_overlay()


def render_skeleton_circle(*, size_px: int = 64) -> Any:
    _ = size_px
    return render_spinner_overlay()


__all__ = [
    'render_spinner_overlay',
    'render_skeleton',
    'render_skeleton_row',
    'render_skeleton_card',
    'render_skeleton_circle',
    'replace_with_real',
]
