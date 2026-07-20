# app/components/drawer.py

"""Left drawer (MENU list) — ported from engine_root."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from app.ui.button_feedback import (
    apply_feedback_classes,
    attach_pointer_feedback,
    set_persistent_active,
)


@dataclass(frozen=True)
class DrawerMenuItem:
    """Menu item shown inside the control panel left drawer."""

    label: str
    target: str | None = None


CONTROL_MENU_TITLE = 'MENU'

ACTIVE_MENU_CLASSES = 'drawer-menu-item-active menu-item-active'

# Buttons on the left drawer render against the dark control-panel
# surface, so we attach the dark variant of the feedback CSS class.
DRAWER_BUTTON_VARIANT = 'dark'


def render_drawer_title() -> None:
    ui.label(CONTROL_MENU_TITLE).classes('drawer-menu-title menu-title')


def render_drawer_menu_separator() -> None:
    ui.separator().classes('drawer-menu-red-separator')


def render_drawer_menu_item(
    item: DrawerMenuItem,
    *,
    menu_buttons: list[Any],
    active_label: str | None,
    on_click: Callable[[DrawerMenuItem], None] | None = None,
) -> None:
    button = (
        ui.button(
            item.label,
            color=None,
        )
        .props('flat no-caps align=left')
        .classes('drawer-menu-item menu-item')
    )

    # Sub-16 ms pointer feedback — the button gains the
    # ``.btn-feedback--dark`` class so its pressed state lights
    # up immediately when the user clicks, with no server
    # round-trip. See ``app.ui.button_feedback`` for details.
    apply_feedback_classes(button, variant=DRAWER_BUTTON_VARIANT)
    attach_pointer_feedback(button)

    menu_buttons.append(button)

    def set_active() -> None:
        for menu_button in menu_buttons:
            menu_button.classes(remove=ACTIVE_MENU_CLASSES)
            # The persistent-active accent (left-edge bar) is part
            # of the same visual language; clear it on every
            # sibling so only the new owner carries the accent.
            set_persistent_active(menu_button, False)

        button.classes(ACTIVE_MENU_CLASSES)
        set_persistent_active(button, True)

    def handle_click() -> None:
        set_active()

        if on_click:
            on_click(item)
            return

        if item.target:
            ui.navigate.to(item.target)
            return

        ui.notify(f'Selected: {item.label}')

    button.on('click', lambda _: handle_click())

    if active_label == item.label:
        button.classes(ACTIVE_MENU_CLASSES)
        set_persistent_active(button, True)


def render_drawer_menu_items(
    items: tuple[DrawerMenuItem, ...],
    *,
    active_label: str,
    on_item_click: Callable[[DrawerMenuItem], None] | None = None,
) -> None:
    menu_buttons: list[Any] = []

    with ui.column().classes('drawer-menu-list gap-0'):
        for item in items:
            render_drawer_menu_item(
                item,
                menu_buttons=menu_buttons,
                active_label=active_label,
                on_click=on_item_click,
            )


def create_control_panel_left_drawer(
    *,
    items: tuple[DrawerMenuItem, ...],
    active_label: str,
    on_item_click: Callable[[DrawerMenuItem], None] | None = None,
):
    """Create control panel left drawer."""
    left_drawer = (
        ui.left_drawer(
            value=False,
            fixed=True,
            bordered=False,
            elevated=False,
            top_corner=False,
            bottom_corner=False,
        )
        .classes('control-left-drawer left-bar')
        .props('behavior=desktop width=260')
    )

    with left_drawer:
        with ui.column().classes('control-left-drawer-content'):
            render_drawer_title()
            render_drawer_menu_separator()

            render_drawer_menu_items(
                items,
                active_label=active_label,
                on_item_click=on_item_click,
            )

    return left_drawer
