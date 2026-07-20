# app/components/footer.py

"""Footer — ported from engine_root."""

from nicegui import ui

FOOTER_TEXT = '© 2026 ChemPlant Dynamics. All rights reserved.'


def render_footer_text() -> None:
    ui.label(FOOTER_TEXT).classes('footer-text')


def build_footer() -> None:
    with ui.footer().classes('app-footer'):
        with ui.row().classes('app-footer-inner items-center no-wrap'):
            with ui.row().classes('footer-region footer-left items-center justify-start no-wrap'):
                render_footer_text()
