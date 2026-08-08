# app/components/popout_button.py

from nicegui import ui


def render_popout_button(
    url: str,
    tooltip: str = 'New Tab',
    classes: str = '',
) -> None:
    """Render a flat dense icon button to open a URL in a new tab."""

    def _open() -> None:
        # Always open in a brand new tab
        ui.run_javascript(f"window.open('{url}', '_blank')")

    with (
        ui.button(icon='open_in_new', on_click=_open, color=None)
        .props('flat dense round')
        .classes(f'popout-icon-btn {classes}')
    ):
        ui.tooltip(tooltip)
