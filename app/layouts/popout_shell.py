# app/layouts/popout_shell.py

"""Pop-out page shell.

Mirrors the control-panel shell layout but without the left drawer and
menu button. Used for independent tabs (PID, Perf Mon, Data Logger).
"""

from collections.abc import Callable

from nicegui import ui

from app.components.footer import build_footer
from app.components.header import build_popout_header
from app.layouts.shell import setup_page_shell


def popout_shell(
    page_title: str,
    content: Callable[[], None],
    subtitle: str | None = None,
    title_classes: str = ('text-lg font-bold tracking-wide text-white/90 uppercase'),
    subtitle_classes: str = (
        'text-xs text-white/60 ml-2 mt-1 tracking-wider uppercase font-semibold'
    ),
) -> None:
    """Pop-out shell layout."""
    setup_page_shell(body_class='control-panel-page control-panel-drawer-closed')

    # Header without menu button, with page title
    build_popout_header(
        page_title,
        _subtitle=subtitle,
        _title_classes=title_classes,
        _subtitle_classes=subtitle_classes,
    )

    # Use the established control panel classes for the fixed layout
    with ui.column().classes('control-panel-main main-content w-full'):
        with ui.column().classes('control-panel-content-stack w-full'):
            with ui.column().classes(
                'w-full h-full flex-1 min-h-0 p-0 m-0 gap-0 overflow-auto relative'
            ):
                content()

    build_footer()
