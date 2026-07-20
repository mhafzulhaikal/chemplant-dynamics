# app/components/right_drawer.py

"""PID right drawer — legacy content panel.

The current control-panel pages build the right drawer inline and hand
it to :class:`app.components.faceplate.FaceplatePanel` (see
``app.pages.sthr_page`` / ``app.pages.biodiesel_page``). This module is
kept for backward compatibility — it exposes a small helper that renders
a static "PID Tools" list with the same CSS classes the new drawer uses,
so older callers (or unit tests that import this module) keep working.

The render function does *not* own the ``<aside>`` element; the host
page is responsible for creating the drawer container. See
``app.layouts.shell`` and the per-case pages for the wiring.
"""

from __future__ import annotations

from nicegui import ui


def render_pid_right_drawer_content() -> None:
    """Render the static "PID Tools" content into the current drawer.

    Caller is expected to have already opened the
    ``.pid-right-drawer`` aside element. This is the legacy content
    panel; the faceplate in :mod:`app.components.faceplate` is the
    primary right-drawer surface in the current dashboard.
    """
    with ui.column().classes('pid-right-drawer-content'):
        ui.label('PID Tools').classes('pid-right-drawer-title')

        ui.separator().classes('pid-right-drawer-separator')

        ui.label('Control Parameters').classes('pid-right-drawer-section-title')

        ui.label('TIC-100').classes('pid-right-drawer-item')
        ui.label('FI-100').classes('pid-right-drawer-item')
        ui.label('FI-101').classes('pid-right-drawer-item')
        ui.label('TI-100').classes('pid-right-drawer-item')
        ui.label('LI-100').classes('pid-right-drawer-item')


__all__ = ['render_pid_right_drawer_content']
