# app/components/header.py

"""Header component — home and control-panel variants.

Clicking the app title navigates to (or focuses) the home tab via
:func:`navigate_to_home`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from nicegui import ui

APP_TITLE = 'ChemPlant Dynamics'

HEADER_LOGO = '/static/assets/logos/unri_white.png'
HEADER_LOGO_TOOLTIP = 'University of Riau'

ORG_LOGO = '/static/assets/logos/logo_unri.png'
ORG_LOGO_TOOLTIP = 'University of Riau'

ORG_LINE_1 = 'Process Design and Control Laboratory'
ORG_LINE_2 = 'Department of Chemical Engineering'
ORG_LINE_3 = 'University of Riau'

# window.open reuses a tab with the same name.
HOME_TAB_NAME = 'chemplant-home'
HOME_URL = '/'


def navigate_to_home() -> None:
    """Focus the existing home tab or open a new one."""
    ui.run_javascript(f"""
        (function() {{
            var url = {HOME_URL!r};
            var name = {HOME_TAB_NAME!r};
            var w = window.open(url, name);
            if (w) {{
                try {{ w.focus(); }} catch (_) {{}}
                return;
            }}
            window.location.href = url;
        }})();
        """)


class HeaderVariant(StrEnum):
    HOME = 'home'
    CONTROL_PANEL = 'control-panel'


@dataclass(frozen=True)
class HeaderConfig:
    variant: HeaderVariant

    show_menu_button: bool = False
    show_title: bool = True

    show_center_identity: bool = False
    center_identity_align: str = 'center'

    show_right_identity: bool = False
    right_identity_align: str = 'right'
    show_header_logo: bool = True
    show_org_logo: bool = False


def render_menu_button(on_click: Callable | None = None) -> None:
    ui.button(
        icon='menu',
        on_click=on_click,
        color=None,
    ).props('flat round dense').classes('header-menu-button')


def render_header_title(on_click: Callable[[], None] | None = None) -> None:
    """Render the app title.

    Optionally clickable.
    """
    label = ui.label(APP_TITLE).classes('app-title')
    if on_click is not None:
        label.classes(add='app-title-clickable')
        label.props('role=button tabindex=0 aria-label="Go to home"')
        try:
            label.on('click', on_click)
        except Exception:
            try:
                label.on_click(on_click)  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            label.on(
                'keydown',
                lambda e: (
                    on_click()
                    if (
                        isinstance(e.args, dict)
                        and str(e.args.get('key', '')).lower() in ('enter', ' ')
                    )
                    else None
                ),
            )
        except Exception:
            pass


def render_header_logo() -> None:
    with ui.row().classes('header-logo-row items-center justify-center no-wrap'):
        logo = ui.image(HEADER_LOGO).classes('header-logo-image').props('fit=contain no-spinner')
        logo.tooltip(HEADER_LOGO_TOOLTIP)


def render_org_logo() -> None:
    with ui.row().classes('org-logo-row items-center justify-center no-wrap'):
        logo = ui.image(ORG_LOGO).classes('org-logo-image').props('fit=contain no-spinner')
        logo.tooltip(ORG_LOGO_TOOLTIP)


def render_organization_identity(align: str = 'right') -> None:
    if align == 'center':
        block_class = 'org-block org-block-center gap-1'
    else:
        block_class = 'org-block org-block-right gap-1'

    with ui.column().classes(block_class):
        ui.label(ORG_LINE_1).classes('org-line-1')
        ui.label(ORG_LINE_2).classes('org-line-2')
        ui.label(ORG_LINE_3).classes('org-line-3')


def build_header(
    config: HeaderConfig,
    on_menu_click: Callable | None = None,
    on_title_click: Callable[[], None] | None = None,
) -> None:
    with ui.header().classes(f'app-header {config.variant.value}-header'):
        with ui.row().classes('app-header-inner items-center no-wrap'):
            # LEFT
            with ui.row().classes('header-region header-left items-center justify-start no-wrap'):
                if config.show_menu_button:
                    render_menu_button(on_menu_click)

                if config.show_title:
                    render_header_title(on_title_click)

            # CENTER
            with ui.row().classes(
                'header-region header-center items-center justify-center no-wrap'
            ):
                if config.show_center_identity:
                    render_organization_identity(config.center_identity_align)

            # RIGHT
            with ui.row().classes('header-region header-right items-center justify-end no-wrap'):
                if config.show_right_identity:
                    render_organization_identity(config.right_identity_align)

                if config.show_org_logo:
                    render_org_logo()

                if config.show_header_logo:
                    render_header_logo()


def build_home_header(
    on_title_click: Callable[[], None] | None = None,
) -> None:
    cfg = HeaderConfig(
        variant=HeaderVariant.HOME,
        show_menu_button=False,
        show_title=True,
        show_center_identity=False,
        show_right_identity=True,
        show_header_logo=True,
        show_org_logo=False,
    )
    build_header(
        cfg,
        on_title_click=on_title_click or navigate_to_home,
    )


def build_control_panel_header(
    on_menu_click: Callable | None = None,
    on_title_click: Callable[[], None] | None = None,
) -> None:
    cfg = HeaderConfig(
        variant=HeaderVariant.CONTROL_PANEL,
        show_menu_button=True,
        show_title=True,
        show_center_identity=True,
        center_identity_align='center',
        show_header_logo=True,
        show_org_logo=True,
    )
    build_header(
        cfg,
        on_menu_click=on_menu_click,
        on_title_click=on_title_click or navigate_to_home,
    )


def build_popout_header(
    _page_title: str,
    _subtitle: str | None = None,
    on_title_click: Callable[[], None] | None = None,
    _title_classes: str = ('text-lg font-bold tracking-wide text-white/90 uppercase'),
    _subtitle_classes: str = (
        'text-xs text-white/60 ml-2 mt-1 tracking-wider uppercase font-semibold'
    ),
) -> None:
    cfg = HeaderConfig(
        variant=HeaderVariant.HOME,
        show_menu_button=False,
        show_title=True,
        show_center_identity=False,
        show_right_identity=True,
        show_header_logo=True,
        show_org_logo=False,
    )
    build_header(
        cfg,
        on_title_click=on_title_click or navigate_to_home,
    )
