# app/ui/cell_labels.py

"""Shared custom-label registry for Data Logger and Performance Monitor cells.

Both the Data Logger and Performance Monitor render clickable header cells
whose tag text defaults to the bridge field name (e.g. ``TIC-100.SP``).
This module provides a per-page registry so the operator can rename any
cell's display label without affecting the underlying field mapping.

Labels are stored in a ``dict[str, str]`` keyed by the full field name
(``output:TIC-100.SP``). Both modules import the same ``custom_labels``
dict instance so a rename in the Data Logger is visible in the
Performance Monitor on the next refresh, and vice versa.

The rename UI uses NiceGUI's ``ui.dialog`` with a ``ui.input`` — follows
the Quasar dialog pattern (``persistent``, ``@hide`` cleanup).
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

custom_labels: dict[str, str] = {}


def get_label(field_name: str, default: str) -> str:
    return custom_labels.get(field_name, default)


def open_rename_dialog(
    field_name: str,
    current_display: str,
    on_confirm: Any,
) -> None:
    with ui.dialog().props('persistent') as dialog, ui.card().classes('cell-rename-dialog'):
        ui.label('RENAME CELL').classes('cell-rename-dialog-title')
        rename_input = (
            ui.input(
                value=current_display,
            )
            .props(
                'dense borderless autofocus',
            )
            .classes('cell-rename-dialog-input')
        )

        with ui.row().classes('cell-rename-dialog-actions'):
            ui.button(
                'CANCEL',
                on_click=dialog.close,
            ).props('flat no-caps dense').classes(
                'cell-rename-dialog-btn cell-rename-dialog-btn-cancel',
            )

            def _confirm() -> None:
                new_label = str(rename_input.value or '').strip()
                if new_label and new_label != default_label_raw(field_name):
                    custom_labels[field_name] = new_label
                elif field_name in custom_labels:
                    del custom_labels[field_name]
                dialog.close()
                if on_confirm is not None:
                    on_confirm()

            ui.button(
                'RENAME',
                on_click=_confirm,
            ).props('flat no-caps dense').classes(
                'cell-rename-dialog-btn cell-rename-dialog-btn-confirm',
            )

    dialog.open()


def default_label_raw(field_name: str) -> str:
    _, _, tag = field_name.partition(':')
    return tag.upper()
