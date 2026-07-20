# app/hub/children/modals/base.py

"""Tunable :class:`ControllerModal` (the dialog shown when an operator clicks a
controlling element in the P&ID SVG).

Rewritten from the legacy ``app/pid/sthr/controller_modal.py``
during the v1 purge. The visual layout, JS hover effects, mode
badge sync, post-reset suppress flag, and faceplate hook are
preserved byte-for-byte — the rewrite is purely a relocation +
file split.

API contract (kept stable so v2 views only had to change import
paths):

- ``__init__(store, html_element, controller_tag, param_keys,
              param_defaults=None, title=None)``
- ``controller_tag``, ``controller_svg_id``, ``store``,
  ``dialog_is_open``, ``mode_options``, ``has_tuning``,
  ``supports_operator_output``, ``mode_select``, ``sp_input``,
  ``pv_input``, ``op_input``, ``kc_input``, ``taui_input``,
  ``taud_input``, ``apply_button``, ``param_keys``, ``param_defaults``
- ``refresh_modal_values(force_op_refresh=False, force_sp_refresh=False)``
- ``apply_mode_state(status=None)``
- ``read_only_map(status=None)``
- ``_selected_status()``
- ``_apply_numeric_value(field_name, field)``
- ``commit_mode_change(status, include_tuning)``
- ``apply_dialog_values()``
- ``set_faceplate(faceplate)`` / ``open_faceplate()``
- ``open(left=None, top=None, right=None, bottom=None)``
- ``handle_svg_click(e)``
- ``_default_value(key, fallback)``
- ``_set_field_value(field, value)`` — guarded by the focus tracker
- (transient) ``_suppress_input_push`` — set by FaceplateChild after
  a reset for one tick.
"""

from __future__ import annotations

import re
from typing import Any

from nicegui import ui

from app.hub.input_focus_tracker import (
    attach_focus_tracker,
    is_user_editing,
)
from app.hub.local_store import LocalStore
from app.pid.biodiesel.ui_config import (
    CONTROLLER_DRAWER_CONFIG as BIODIESEL_CONTROLLER_DRAWER_CONFIG,
)
from app.pid.sthr.ui_config import CONTROLLER_DRAWER_CONFIG as STHR_CONTROLLER_DRAWER_CONFIG
from app.pid.sthr.ui_config import DISPLAY_MAP as STHR_DISPLAY_MAP

__all__ = ['ControllerModal']


class ControllerModal:
    """Generic controller modal used for different controller types."""

    def __init__(
        self,
        store: LocalStore,
        html_element: ui.element,
        controller_tag: str,
        param_keys: dict[str, str],
        param_defaults: dict[str, Any] | None = None,
        title: str | None = None,
    ) -> None:
        self.store = store
        self.html_element = html_element
        self.controller_tag = str(controller_tag).strip().upper()
        self.controller_svg_id = self.controller_tag.lower()
        self.param_keys = param_keys
        _is_biodiesel = 'biodiesel' in type(self).__module__
        self.is_biodiesel = _is_biodiesel
        _cfg_src = (
            BIODIESEL_CONTROLLER_DRAWER_CONFIG if _is_biodiesel else STHR_CONTROLLER_DRAWER_CONFIG
        )
        self.drawer_cfg = (
            _cfg_src.get(self.controller_svg_id, {}) if isinstance(_cfg_src, dict) else {}
        )
        drawer_label = self.drawer_cfg.get('label') if isinstance(self.drawer_cfg, dict) else None
        self.title = title or str(drawer_label or f'{self.controller_tag} Parameters')

        self.dialog_is_open = False
        self.mode_syncing = False

        self.param_defaults = param_defaults or {}
        self.mode_options = {
            'off': 'Off',
            'manual': 'Manual',
            'auto': 'Automatic',
        }

        self.sp_unit = self._display_unit(self.controller_tag)
        self.pv_unit = self._display_unit(self.controller_tag)
        self.op_unit = '%CO'
        self._kc_unit_fallback = '%CO/%TO'
        self._tau_unit_fallback = 'minutes'
        self.supports_operator_output = bool(self._engine_key('op'))

        self.mode_select: ui.select | None = None
        self.status_select: ui.select | None = None
        self.mode_badge = None
        self.mode_badge_dot = None
        self.mode_badge_text = None
        self.field_refs: dict[str, ui.number] = {}

        # Optional reference to the right-drawer faceplate. When
        # the host page wires the faceplate in, clicking the modal's
        # "Face plate" button opens the drawer with this
        # controller's PV/SP/OP bargraphs instead of showing a no-op
        # notification.
        self._faceplate: Any = None

        self.sp_input: ui.number | None = None
        self.pv_input: ui.number | None = None
        self.op_input: ui.number | None = None
        self.kc_input: ui.number | None = None
        self.taui_input: ui.number | None = None
        self.taud_input: ui.number | None = None

        self.has_tuning = all(self._engine_key(key) for key in ('kc', 'tau_i', 'tau_d'))

        # Unique per-modal CSS class so the smart-placement JS
        # selectors only ever target THIS modal's card — there can
        # be a dozen modals on a single PID page (one per
        # controller) and they all share the
        # ``.ctrl-param-dialog-card`` class. Without a per-instance
        # discriminator a ``document.querySelector('.ctrl-param-dialog-card')``
        # would pick the first one in the DOM, not the one that
        # was just opened.
        self._dialog_uid = f'ctrl-param-uid-{id(self):x}'

        # Build dialog
        _menu_props = (
            f'target="#{self.controller_svg_id}"'
            ' anchor="bottom left" self="top left"'
            ' :offset="[0, 8]" transition-show="scale"'
            ' transition-hide="scale" persistent'
        )
        with (
            ui.menu()
            .props(_menu_props)
            .classes(
                'bg-transparent shadow-none overflow-hidden',
            )
            .style('border-radius: 8px') as self.dialog,
            ui.card().classes(
                f'ctrl-param-dialog-card {self._dialog_uid}',
            ) as self.dialog_card,
        ):
            # Header — faceplate-style: tag + short title cluster
            # on the left, mode badge + close button in a single
            # right cluster. Markup mirrors :meth:`FaceplatePanel.render`
            # exactly (same ``ui.row``/``ui.column`` nesting, same
            # ``no-wrap`` Quasar prop) so the modal and the
            # persistent right-drawer faceplate read as a single
            # control surface.
            with ui.row().classes('ctrl-param-dialog-header no-wrap'):
                with ui.column().classes('ctrl-param-dialog-header-text'):
                    ui.label(self.controller_tag).classes(
                        'ctrl-param-dialog-tag',
                    )
                    short_title = self.title
                    if ' — ' in short_title:
                        short_title = short_title.split(' — ', 1)[1]
                    ui.label(short_title).classes(
                        'ctrl-param-dialog-title',
                    )

                with ui.row().classes(
                    'ctrl-param-dialog-header-right no-wrap',
                ):
                    if self._engine_key('status'):
                        with ui.row().classes(
                            'ctrl-param-mode-badge',
                        ) as badge_row:
                            self.mode_badge = badge_row
                            self.mode_badge_dot = ui.element('span').classes(
                                'ctrl-param-status-dot ctrl-param-status-auto',
                            )
                            self.mode_badge_text = ui.label('AUTO').classes(
                                'ctrl-param-mode-text',
                            )

                    ui.button(
                        icon='close',
                        color=None,
                        on_click=self.dialog.close,
                    ).props('flat round dense size=sm').classes(
                        'ctrl-param-close-btn',
                    )

            with ui.column().classes('ctrl-param-dialog-content'):
                self._build_operation_section()
                if self.has_tuning:
                    self._build_tuning_section()

            with ui.row().classes('ctrl-param-footer w-full'):
                ui.button('Face plate', on_click=self.open_faceplate).props('flat dense').classes(
                    'ctrl-param-faceplate-btn'
                )
                self.apply_button = (
                    ui.button('Apply', on_click=self.apply_dialog_values)
                    .props('flat dense')
                    .classes('ctrl-param-apply-btn')
                )

        # Bind events
        if self.mode_select is not None:
            self.mode_select.on_value_change(self.on_mode_change)
        self.dialog.on('hide', self.hide_dialog)

        self._install_svg_hooks()
        try:
            self.refresh_modal_values(force_op_refresh=True)
        except Exception:
            import os
            import tempfile
            import traceback

            log_path = os.path.join(
                tempfile.gettempdir(),
                'app_modal_trace.log',
            )
            with open(log_path, 'a', encoding='utf-8') as _f:
                _tag = self.controller_tag
                _f.write(f'=== {_tag} refresh_modal_values FAILED ===\n')
                traceback.print_exc(file=_f)
                _f.write('\n')
            raise

    # -------------------------------
    # Helpers — labels, units, meta
    # -------------------------------

    def _display_unit(self, tag: str) -> str:
        key = str(tag).strip().lower()

        # 1. Ask the hub registry (engine-connected case) — this avoids
        #    collisions when STHR and biodiesel share the same SVG id.
        hub = getattr(self.store, '_hub', None)
        if hub is not None:
            registry = getattr(hub, 'registry', None)
            if registry is not None:
                try:
                    spec = registry.by_svg_id(key)
                    if spec is not None and spec.unit:
                        return str(spec.unit)
                except Exception:
                    pass

        # 2. Legacy global DISPLAY_MAP (pure-UI / STHR-only cases).
        cfg = STHR_DISPLAY_MAP.get(key, {}) if isinstance(STHR_DISPLAY_MAP, dict) else {}
        unit = str(cfg.get('unit', ''))
        if unit:
            return unit

        # 3. Generic fallback for biodiesel controllers not in the map.
        tag_upper = key.upper()
        if tag_upper.startswith('FIC') or tag_upper.startswith('FI'):
            return 'm³/h'
        if tag_upper.startswith('LIC'):
            return 'm'
        if tag_upper.startswith('TIC') or tag_upper.startswith('TI'):
            return 'K'
        if tag_upper.startswith('PI'):
            return 'bar'
        return ''

    def _engine_key(self, ui_key: str) -> str | None:
        value = self.param_keys.get(ui_key)
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _param_meta(self, ui_key: str) -> dict[str, Any]:
        params = self.drawer_cfg.get('params', []) if isinstance(self.drawer_cfg, dict) else []
        engine_field = self._engine_key(ui_key)

        for item in params:
            if not isinstance(item, dict):
                continue
            item_field = str(item.get('field', '')).strip()
            item_key = str(item.get('key', '')).strip()
            if (engine_field and item_field == engine_field) or item_key == ui_key:
                return {
                    'min': item.get('min'),
                    'max': item.get('max'),
                    'step': item.get('step', 0.01),
                    'label': item.get('label'),
                }

        return {'min': None, 'max': None, 'step': 0.01, 'label': None}

    def _unit_from_label(self, label: str | None) -> str:
        text = str(label or '').strip()
        if not text:
            return ''

        match = re.search(r'\(([^)]+)\)', text)
        if match:
            return str(match.group(1)).strip()

        lowered = text.lower()
        if lowered.endswith(' min'):
            return 'min'
        if lowered.endswith(' minutes'):
            return 'minutes'

        return ''

    def _sp_row_label(self) -> str:
        sp_field = str(self._engine_key('sp') or '').strip().lower()
        if sp_field == 'sp':
            return 'SP'
        if sp_field == 'feed_flow':
            return 'F'
        if sp_field == 'feed_temp':
            return 'Ti'
        return 'SP'

    def _sp_row_unit(self) -> str:
        sp_meta = self._param_meta('sp')
        from_label = self._unit_from_label(sp_meta.get('label'))
        if from_label:
            return from_label
        return self.sp_unit

    def _row_label_from_meta(self, ui_key: str, fallback: str) -> str:
        meta = self._param_meta(ui_key)
        raw_label = str(meta.get('label') or '').strip()
        if not raw_label:
            return fallback

        no_unit = re.sub(r'\s*\([^)]*\)\s*', '', raw_label)
        compact = no_unit.replace('Time', '').replace('time', '').strip()
        if not compact:
            return fallback

        lower = compact.lower()
        if lower.startswith('gain'):
            return 'Kc'
        if 'integral' in lower:
            return 'tauI'
        if 'derivative' in lower:
            return 'tauD'

        return fallback

    def _row_unit_from_meta(self, ui_key: str, fallback: str) -> str:
        meta = self._param_meta(ui_key)
        raw_label = str(meta.get('label') or '').strip()
        if not raw_label:
            return fallback

        if ui_key in {'kc', 'tau_i', 'tau_d'}:
            lower = raw_label.lower()
            if lower.endswith(' min'):
                return 'min'
            if lower.endswith(' minutes'):
                return 'minutes'
            if lower.endswith(' sec'):
                return 'sec'
            if lower.endswith(' seconds'):
                return 'seconds'
            if '%' in raw_label or '/' in raw_label:
                parsed = self._unit_from_label(raw_label)
                return parsed or fallback
            return fallback

        from_label = self._unit_from_label(raw_label)
        return from_label or fallback

    def _default_value(self, key: str, fallback: float) -> float:
        value = self.param_defaults.get(key, fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    def _coerce_float(self, value: Any) -> float | None:
        if value in (None, ''):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def _is_flow_controller(self) -> bool:
        """True when this controller's PV/SP are per-second flow rates."""
        tag = self.controller_tag.upper()
        return tag.startswith('FIC') or tag.startswith('FI')

    @property
    def kc_unit(self) -> str:
        return self._row_unit_from_meta('kc', self._kc_unit_fallback)

    @property
    def taui_unit(self) -> str:
        return self._row_unit_from_meta('tau_i', self._tau_unit_fallback)

    @property
    def taud_unit(self) -> str:
        return self._row_unit_from_meta('tau_d', self._tau_unit_fallback)

    @property
    def value_keys(self) -> dict[str, str | None]:
        return {
            'pv': self._engine_key('pv'),
            'sp': self._engine_key('sp'),
            'op': self._engine_key('op'),
            'kc': self._engine_key('kc'),
            'tau_i': self._engine_key('tau_i'),
            'tau_d': self._engine_key('tau_d'),
            'status': self._engine_key('status'),
        }

    @property
    def modal_type(self) -> str:
        return 'controller'

    def _set_field_value(
        self,
        field: ui.number | None,
        value: Any,
        decimals: int | None = None,
    ) -> None:
        if field is None:
            return

        # ── Guard: skip the overwrite while the operator is typing ──
        # The hub's ModalChild calls ``refresh_modal_values`` every
        # tick, which in turn writes every input via this method.
        # Without this guard, an operator typing a new SP gets
        # clobbered every 50 ms by the snapshot value.
        if is_user_editing(field):
            return

        format_changed = False
        if decimals is not None and getattr(field, '_props', {}).get('readonly'):
            new_fmt = f'%.{decimals}f'
            if getattr(field, 'format', None) != new_fmt:
                field.format = new_fmt
                # Force NiceGUI to re-evaluate _value_to_model_value
                field._value = None  # type: ignore
                format_changed = True
        else:
            if getattr(field, 'format', None) is not None:
                field.format = None
                field._value = None  # type: ignore
                format_changed = True
            if hasattr(field, '_props') and 'format' in field._props:
                field._props.pop('format', None)
                field._value = None  # type: ignore
                format_changed = True

        if value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError):
                pass

        # ── Skip the write if the value is already in sync ──
        # Avoids triggering a no-op ``on_value_change`` round-trip
        # and keeps the per-tick cost down to a no-op when the
        # engine hasn't actually moved the value.
        if not format_changed:
            try:
                current = field.value
                if (
                    current is not None
                    and current != ''
                    and value is not None
                    and float(current) == float(value)
                ):
                    return
            except (TypeError, ValueError):
                pass
        field.value = value  # type: ignore

    def _field_engine_key(self, field_name: str) -> str | None:
        key_map = {
            'SP': 'sp',
            'PV': 'pv',
            'OP': 'op',
            'Kc': 'kc',
            'tauI': 'tau_i',
            'tauD': 'tau_d',
        }
        ui_key = key_map.get(field_name)
        return self._engine_key(ui_key) if ui_key else None

    def _apply_numeric_value(self, field_name: str, field: ui.number) -> None:
        """Write the value into the local store (engine replacement)."""
        value = self._coerce_float(field.value)
        if value is None:
            return
        engine_key = self._field_engine_key(field_name)
        if engine_key:
            self.store.set(engine_key, value)

    # -------------------------------
    # UI builders
    # -------------------------------

    def _build_number_row(
        self,
        label: str,
        field_name: str,
        default_key: str,
        unit: str,
        *,
        min_value: float | None,
        max_value: float | None,
        step: float,
        precision: int = 2,
        extra_classes: str = '',
    ) -> ui.number:
        with ui.element('div').classes('ctrl-param-row'):
            ui.label(label).classes('ctrl-param-variable')
            field = self._number_field(
                field_name,
                self._default_value(default_key, 0.0),
                precision=precision,
                min_value=min_value,
                max_value=max_value,
                step=step,
                extra_classes=extra_classes,
            )
            ui.label(unit).classes('ctrl-param-unit')
        return field

    def _set_readonly(self, field: ui.number | None, readonly: bool) -> None:
        if field is None:
            return
        if readonly:
            field.props('readonly')
            field.classes(add='ctrl-param-readonly-value')
        else:
            field.props(remove='readonly')
            field.classes(remove='ctrl-param-readonly-value')
            field.format = None
            if hasattr(field, '_props'):
                field._props.pop('format', None)
            field.update()

    def _number_field(
        self,
        name: str,
        value: float,
        precision: int = 2,
        min_value: float | None = None,
        max_value: float | None = None,
        step: float = 0.01,
        extra_classes: str = '',
    ) -> ui.number:
        field = (
            ui.number(
                value=value,
                format=None,
                min=min_value,
                max=max_value,
                step=step,
            )
            .props(
                'dense step=any color="amber" '
                f'tooltip="Press Enter or click Apply to commit {name}"',
            )
            .classes(f'ctrl-param-value {extra_classes}'.strip())
        )
        self.field_refs[name] = field

        # ── Commit on blur or Enter only ──
        # The value is held in the input until the operator confirms
        # by pressing Enter, tabbing/blurring out of the field, or
        # clicking the dialog's Apply button. The Apply path goes
        # through :meth:`apply_dialog_values` → :meth:`commit_mode_change`
        # which iterates every field and writes the value, so Apply
        # still works as a "commit all" action.
        def _commit(_=None, fld=field, key=name):
            self._apply_numeric_value(key, fld)

        for evt in ('blur', 'keydown.enter'):
            try:
                field.on(evt, _commit)
            except Exception:
                pass

        # ── Focus tracker ──
        # Wires DOM focus/blur to a transient ``_user_is_editing``
        # flag on the field. ``_set_field_value`` consults this flag
        # so the per-tick refresh doesn't clobber a value the
        # operator is typing.
        attach_focus_tracker(field)

        return field

    def _build_mode_row(self) -> None:
        with ui.element('div').classes('ctrl-param-row'):
            ui.label('Mode').classes('ctrl-param-variable')
            self.mode_select = (
                ui.select(options=self.mode_options, value='auto')
                .props('dense borderless popup-content-class="ctrl-param-mode-popup"')
                .classes('ctrl-param-mode')
            )
            self.status_select = self.mode_select
            ui.label('').classes('ctrl-param-unit')

    def _build_operation_section(self) -> None:
        sp_meta = self._param_meta('sp')
        sp_label = self._sp_row_label()
        sp_unit = self._sp_row_unit()
        sp_min = sp_meta.get('min') if sp_meta.get('min') is not None else 0.0
        sp_max = sp_meta.get('max') if sp_meta.get('max') is not None else 1000.0
        sp_step = float(sp_meta.get('step', 0.01) or 0.01)

        pv_meta = self._param_meta('pv')
        pv_min = pv_meta.get('min') if pv_meta.get('min') is not None else sp_min
        pv_max = pv_meta.get('max') if pv_meta.get('max') is not None else sp_max
        pv_step = float(pv_meta.get('step', sp_step) or sp_step)

        op_meta = self._param_meta('op')
        op_min = op_meta.get('min') if op_meta.get('min') is not None else 0.0
        op_max = op_meta.get('max') if op_meta.get('max') is not None else 100.0
        op_step = float(op_meta.get('step', 0.01) or 0.01)

        with ui.card().tight().classes('ctrl-param-section'):
            ui.label('Operational Parameters').classes('ctrl-param-section-title')
            with ui.element('div').classes('ctrl-param-inputs'):
                if self._engine_key('status'):
                    self._build_mode_row()
                self.sp_input = self._build_number_row(
                    sp_label,
                    'SP',
                    'sp',
                    sp_unit,
                    min_value=sp_min,
                    max_value=sp_max,
                    step=sp_step,
                )
                self.pv_input = self._build_number_row(
                    'PV',
                    'PV',
                    'pv',
                    self.pv_unit,
                    min_value=pv_min,
                    max_value=pv_max,
                    step=pv_step,
                )

                if self.supports_operator_output:
                    self.op_input = self._build_number_row(
                        'OP',
                        'OP',
                        'op',
                        self.op_unit,
                        min_value=op_min,
                        max_value=op_max,
                        step=op_step,
                    )

    def _build_tuning_section(self) -> None:
        kc_meta = self._param_meta('kc')
        taui_meta = self._param_meta('tau_i')
        taud_meta = self._param_meta('tau_d')
        kc_label = self._row_label_from_meta('kc', 'Kc')
        taui_label = self._row_label_from_meta('tau_i', 'tauI')
        taud_label = self._row_label_from_meta('tau_d', 'tauD')
        kc_unit = self.kc_unit
        taui_unit = self.taui_unit
        taud_unit = self.taud_unit
        kc_min = kc_meta.get('min') if kc_meta.get('min') is not None else 0.0
        taui_min = taui_meta.get('min') if taui_meta.get('min') is not None else 0.0
        taud_min = taud_meta.get('min') if taud_meta.get('min') is not None else 0.0

        with ui.card().tight().classes('ctrl-param-section'):
            ui.label('Controller Parameters').classes('ctrl-param-section-title')
            with ui.element('div').classes('ctrl-param-inputs'):
                self.kc_input = self._build_number_row(
                    kc_label,
                    'Kc',
                    'kc',
                    kc_unit,
                    min_value=kc_min,
                    max_value=kc_meta.get('max'),
                    step=float(kc_meta.get('step', 0.01) or 0.01),
                )
                self.taui_input = self._build_number_row(
                    taui_label,
                    'tauI',
                    'tau_i',
                    taui_unit,
                    min_value=taui_min,
                    max_value=taui_meta.get('max'),
                    step=float(taui_meta.get('step', 0.01) or 0.01),
                )
                self.taud_input = self._build_number_row(
                    taud_label,
                    'tauD',
                    'tau_d',
                    taud_unit,
                    min_value=taud_min,
                    max_value=taud_meta.get('max'),
                    step=float(taud_meta.get('step', 0.01) or 0.01),
                )

    # -------------------------------
    # SVG affordance + click handling
    # -------------------------------

    def _set_active(self, active: bool) -> None:
        ui.run_javascript(f"""(() => {{
            const group = (() => {{
                const el = document.getElementById('{self.controller_svg_id}');
                if (el) return el;
                const all = document.querySelectorAll('[id]');
                for (let i = 0; i < all.length; i++) {{
                    if (all[i].id.toLowerCase() ===
                        '{self.controller_svg_id}') return all[i];
                }}
                return null;
            }})();
            if (group && typeof group.__ctrl_set_active === 'function') {{
                group.__ctrl_set_active({str(bool(active)).lower()});
            }}
        }})();""")

    def _install_svg_hooks(self) -> None:
        ui.run_javascript(f"""
            (() => {{
                const group = (() => {{
                    const el = document.getElementById(
                        '{self.controller_svg_id}');
                    if (el) return el;
                    const all = document.querySelectorAll('[id]');
                    for (let i = 0; i < all.length; i++) {{
                        if (all[i].id.toLowerCase() ===
                            '{self.controller_svg_id}') return all[i];
                    }}
                    return null;
                }})();
                if (!group || group.__ctrl_affordance_attached) return;
                group.__ctrl_affordance_attached = true;
                let isActive = false;

                group.style.cursor = 'pointer';
                group.setAttribute('title',
                    '{self.controller_tag}: click to edit ' +
                    'controller parameters');

                const applyGlow = (active) => {{
                    const nodes = group.querySelectorAll('*');
                    nodes.forEach(node => {{
                        node.style.cursor = 'pointer';
                        node.style.pointerEvents = 'all';
                        if (node.tagName && (
                            node.tagName.toLowerCase() === 'path' ||
                            node.tagName.toLowerCase() === 'rect')) {{
                            node.style.transition = 'stroke 0.15s ease';
                            node.style.stroke = active ? '#ffd600' : '#ffffff';
                        }}
                    }});
                }};
                group.style.pointerEvents = 'all';

                group.__ctrl_set_active = (active) => {{
                    isActive = !!active;
                    applyGlow(isActive);
                }};

                group.addEventListener('mouseenter',
                    () => applyGlow(true));
                group.addEventListener('mouseleave',
                    () => applyGlow(isActive));
            }})();
            """)

        self.html_element.on(
            'click',
            self.handle_svg_click,
            js_handler="""(evt) => {
                const target = evt.target;
                if (!target) return;
                let withId = null;
                if (target.closest) {
                    withId = target.closest('[id]');
                }
                if (!withId && target.id) {
                    withId = target;
                }
                if (!withId) return;
                let id = withId.id;
                // Strip child suffixes so clicks on <text id="x-value"> or
                // <text id="x-tag"> are treated as clicks on controller x.
                if (id.endsWith('-value')) id = id.slice(0, -6);
                else if (id.endsWith('-tag')) id = id.slice(0, -4);
                // Use the bounding rect of the top-level SVG <g> group
                // (the controller card), not the clicked child element.
                // The child (e.g. a <text> or <path>) can be much smaller
                // than the full controller card, so its rect would place the
                // modal incorrectly.
                const group = document.getElementById(id);
                const rectEl = group || withId;
                const rect = rectEl.getBoundingClientRect();
                emit({
                    target_id: id,
                    left:   rect ? rect.left   : null,
                    top:    rect ? rect.top    : null,
                    right:  rect ? rect.right  : null,
                    bottom: rect ? rect.bottom : null,
                });
            }""",
        )

    # -------------------------------
    # Value sync
    # -------------------------------

    def refresh_modal_values(
        self,
        force_op_refresh: bool = False,
        force_sp_refresh: bool = False,
    ) -> None:
        # ── Suppress input push for one tick after a reset ──
        # When the engine bridge is reset, the FaceplateChild /
        # ModalChild set ``_suppress_input_push`` on this modal so
        # the store→input write below is skipped. That keeps the
        # operator's last-typed numeric values visible on screen
        # even though the store was just re-seeded to case-config
        # defaults. The mode badge and the modal's chrome still
        # refresh.
        suppress = bool(getattr(self, '_suppress_input_push', False))

        status = self._resolve_mode()

        if self.mode_select is not None:
            self.mode_syncing = True
            try:
                self.mode_select.value = status
            finally:
                self.mode_syncing = False

        # Keep the faceplate-style mode badge in lockstep with the
        # Mode select. Done here (not only on user-driven
        # ``on_mode_change``) so a store-driven refresh — e.g. the
        # hub pushing AUTO→MANUAL from the engine bridge, or the
        # very first ``refresh_modal_values`` at init time when the
        # store already holds a non-default status — also updates
        # the header badge.
        self._refresh_mode_badge(status)
        self.apply_mode_state(status)

        # ── Skip the input-widget write if we're suppressing the
        #    post-reset push ──
        # The mode badge above is still refreshed (the user didn't
        # type it), but the SP / PV / OP / Kc / tauI / tauD inputs
        # are left as-is so the operator's last-typed value stays
        # visible until they explicitly press Enter or Apply.
        if suppress:
            return

        spec = None
        try:
            from app.components.faceplate import infer_faceplate_spec

            spec = infer_faceplate_spec(self)
        except Exception:
            pass

        sp_decimals = max(spec.sp_decimals if spec else 2, 4)
        pv_decimals = spec.pv_decimals if spec else 2
        op_decimals = max(spec.op_decimals if spec else 2, 4)

        sp_engine_field = self._engine_key('sp')
        if self.sp_input is not None:
            if sp_engine_field in {'feed_flow', 'feed_temp'} and not force_sp_refresh:
                pass
            else:
                key = sp_engine_field or 'sp'
                raw_sp = self.store.get(key, self._default_value('sp', 150.0))
                self._set_field_value(
                    self.sp_input,
                    raw_sp,
                    decimals=sp_decimals,
                )

        if self.pv_input is not None:
            key = self._engine_key('pv') or 'pv'
            raw_pv = self.store.get(key, self._default_value('pv', 150.0))
            self._set_field_value(
                self.pv_input,
                raw_pv,
                decimals=pv_decimals,
            )
            try:
                sp_key = sp_engine_field or 'sp'
                raw_sp = self.store.get(sp_key, self._default_value('sp', 150.0))
                pv_val = float(raw_pv)
                sp_val = float(raw_sp)
                diff = abs(pv_val - sp_val)

                if diff > 0.05 * abs(sp_val):
                    self.pv_input.classes(add='pv-danger', remove='pv-warning')
                elif diff > 0.01 * abs(sp_val):
                    self.pv_input.classes(add='pv-warning', remove='pv-danger')
                else:
                    self.pv_input.classes(remove='pv-warning pv-danger')
            except (ValueError, TypeError):
                self.pv_input.classes(remove='pv-warning pv-danger')

        op_key = self._engine_key('op') or 'op'
        if self.supports_operator_output and self.op_input is not None:
            if status == 'manual' and not force_op_refresh:
                pass
            else:
                self._set_field_value(
                    self.op_input,
                    self.store.get(op_key, self._default_value('op', 82.3)),
                    decimals=op_decimals,
                )

        for field_name, field in (
            ('Kc', self.kc_input),
            ('tauI', self.taui_input),
            ('tauD', self.taud_input),
        ):
            if field is None:
                continue
            engine_key = self._field_engine_key(field_name)
            if not engine_key:
                continue
            if engine_key in self.store.all():
                self._set_field_value(field, self.store.get(engine_key, 0.0), decimals=2)
            else:
                existing = field.value
                if existing in (None, '') or isinstance(existing, str):
                    self._set_field_value(field, 0.0, decimals=2)
                else:
                    self._set_field_value(field, existing, decimals=2)

    def apply_mode_state(self, status: str | None = None) -> None:
        effective_status = (status or self._selected_status()).lower()

        self._set_readonly(self.pv_input, True)
        sp_engine_field = self._engine_key('sp')
        if effective_status == 'auto':
            state = {
                'sp': False,
                'op': True,
                'kc': False,
                'tauI': False,
                'tauD': False,
            }
        elif effective_status == 'manual':
            state = {
                'sp': sp_engine_field not in {'feed_flow', 'feed_temp'},
                'op': False,
                'kc': True,
                'tauI': True,
                'tauD': True,
            }
        else:
            state = {
                'sp': True,
                'op': True,
                'kc': True,
                'tauI': True,
                'tauD': True,
            }

        for field_name, readonly in state.items():
            self._set_readonly(
                {
                    'sp': self.sp_input,
                    'op': self.op_input,
                    'kc': self.kc_input,
                    'tauI': self.taui_input,
                    'tauD': self.taud_input,
                }[field_name],
                readonly,
            )

    def read_only_map(self, status: str | None = None) -> dict[str, bool]:
        """Return per-field readonly flags for the current mode.

        The faceplate uses this to keep its own inputs in lockstep
        with the modal: any time the mode changes (whether the
        edit came from the modal or the drawer), the drawer
        applies the same readonly flags to its inputs. PV is
        always ``True`` (process value is read-only). Mode is
        always ``False`` (the operator can always change the
        mode). The other fields follow :meth:`apply_mode_state`.
        """
        effective_status = (status or self._selected_status()).lower()
        sp_engine_field = self._engine_key('sp')

        if effective_status == 'auto':
            flags = {
                'sp': False,
                'op': True,
                'kc': False,
                'tau_i': False,
                'tau_d': False,
            }
        elif effective_status == 'manual':
            flags = {
                'sp': sp_engine_field not in {'feed_flow', 'feed_temp'},
                'op': False,
                'kc': True,
                'tau_i': True,
                'tau_d': True,
            }
        else:  # 'off' or unknown
            flags = {
                'sp': True,
                'op': True,
                'kc': True,
                'tau_i': True,
                'tau_d': True,
            }

        flags['pv'] = True  # PV is the process value — read-only
        flags['mode'] = False  # the operator can always switch mode
        return flags

    def _selected_status(self) -> str:
        if self.mode_select is None:
            return self._resolve_mode()
        value = str(self.mode_select.value or 'auto').strip().lower()
        return value if value in {'off', 'manual', 'auto'} else 'auto'

    def _resolve_mode(self) -> str:
        status_key = self._engine_key('status')
        status_map = {0.0: 'off', 1.0: 'manual', 2.0: 'auto'}

        # If no status key, check if it's a biodiesel loop mode
        if status_key is None or (
            'biodiesel'
            in getattr(
                getattr(getattr(self.store, '_hub', None), 'bridge', None),
                'case_name',
                '',
            ).lower()
        ):
            if status_key is None and not self.has_tuning and not hasattr(self, 'mode_options'):
                return 'auto'  # Indicator/Readonly fallback
            hub = getattr(self.store, '_hub', None)
            bridge = getattr(hub, 'bridge', None) if hub else None
            if bridge and hasattr(bridge.state, 'loop_modes'):
                loop_id = self.controller_tag
                if '-' in loop_id:
                    parts = loop_id.split('-')
                    if len(parts[0]) == 2 and parts[0].endswith('C'):
                        loop_id = f'{parts[0][0]}IC-{parts[1]}'
                if loop_id in bridge.state.loop_modes:
                    status = str(bridge.state.loop_modes[loop_id]).lower()
                else:
                    status = str(bridge.state.controller_mode or 'auto').lower()
            else:
                status = 'auto'
            if status == 'automatic':
                status = 'auto'
            return status

        # We have a status key, use it
        raw_status = self.store.get(status_key, 2.0)
        try:
            raw_status = float(raw_status)
        except (TypeError, ValueError):
            raw_status = 2.0
        try:
            return status_map.get(round(float(raw_status)), 'auto')
        except TypeError:
            return 'auto'

    def commit_mode_change(self, status: str, include_tuning: bool) -> None:
        status_key = self._engine_key('status')
        normalized_mode = {
            'off': 'Off',
            'manual': 'Manual',
            'auto': 'Automatic',
        }.get(status.lower(), 'Automatic')

        hub = getattr(self.store, '_hub', None)
        bridge = getattr(hub, 'bridge', None) if hub else None
        case_name = getattr(bridge, 'case_name', '').lower() if bridge else ''
        is_multi_loop = 'biodiesel' in case_name

        if is_multi_loop and bridge and hasattr(bridge.state, 'loop_modes'):
            loop_id = self.controller_tag
            if '-' in loop_id:
                parts = loop_id.split('-')
                if len(parts[0]) == 2 and parts[0].endswith('C'):
                    loop_id = f'{parts[0][0]}IC-{parts[1]}'

            bridge.state.loop_modes[loop_id] = normalized_mode
            bridge.apply_runtime_configuration(restart_if_needed=True)
            bridge.persist_profile()
            # Do NOT call self.store.set(status_key) because that triggers a
            # global mode change
        else:
            if status_key:
                code = {'off': 0.0, 'manual': 1.0, 'auto': 2.0}.get(status.lower(), 2.0)
                self.store.set(status_key, code)

        if include_tuning:
            self._apply_commit_value('SP', self.sp_input)
            self._apply_commit_value('Kc', self.kc_input)
            self._apply_commit_value('tauI', self.taui_input)
            self._apply_commit_value('tauD', self.taud_input)

            if self.supports_operator_output and str(status).lower() == 'manual':
                self._apply_commit_value('OP', self.op_input)

        self.refresh_modal_values(force_op_refresh=True)
        self.apply_mode_state(status)

    def _apply_commit_value(
        self,
        field_name: str,
        field: ui.number | None,
        write_setpoint: bool = False,
    ) -> None:
        value = self._coerce_float(field.value if field is not None else None)
        if value is None:
            return
        engine_key = self._field_engine_key(field_name)
        if engine_key:
            self.store.set(engine_key, value)

    # -------------------------------
    # Event handlers
    # -------------------------------

    def on_mode_change(self, _=None) -> None:
        if self.mode_syncing:
            return

        self.mode_syncing = True
        try:
            status = self._selected_status()
            self.commit_mode_change(status, include_tuning=False)
        finally:
            self.mode_syncing = False

        self._refresh_mode_badge()

    def _refresh_mode_badge(self, status: str | None = None) -> None:
        """Update the header mode badge (status dot + text)."""
        try:
            raw = status if status is not None else self._selected_status()
            status = str(raw or 'auto').strip().lower()
        except Exception:
            status = 'auto'

        if self.mode_badge_dot is not None:
            cls_map = {
                'off': 'ctrl-param-status-off',
                'manual': 'ctrl-param-status-manual',
                'auto': 'ctrl-param-status-auto',
            }
            for cls in cls_map.values():
                try:
                    self.mode_badge_dot.classes(remove=cls)
                except Exception:
                    pass
            try:
                self.mode_badge_dot.classes(add=cls_map.get(status, cls_map['auto']))
            except Exception:
                pass

        if self.mode_badge_text is not None:
            try:
                self.mode_badge_text.set_text(status.upper())
            except Exception:
                pass

    def apply_dialog_values(self) -> None:
        if self.mode_syncing:
            return

        try:
            self.mode_syncing = True
            status = self._selected_status()
            self.commit_mode_change(status, include_tuning=True)
        except Exception as exc:
            ui.notify(f'Failed to apply parameters: {exc}', color='negative')
        else:
            ui.notify(f'{self.controller_tag} parameters applied', color='positive')
        finally:
            self.mode_syncing = False

    def hide_dialog(self) -> None:
        self.dialog_is_open = False
        self._set_active(False)
        try:
            from app.hub.data_logger import write_audit_log

            write_audit_log(
                getattr(self.store, 'case_slug', 'sthr'),
                f'Closed Controller Modal for {self.controller_tag}',
                bridge=getattr(self.store, 'bridge', None),
            )
        except Exception:
            pass

    def set_faceplate(self, faceplate: Any) -> None:
        """Attach the right-drawer faceplate to this modal."""
        self._faceplate = faceplate

    def open_faceplate(self) -> None:
        faceplate = getattr(self, '_faceplate', None)
        if faceplate is not None and hasattr(faceplate, 'open_for'):
            try:
                faceplate.open_for(self.controller_tag)
                return
            except Exception:
                pass
        ui.notify(f'{self.controller_tag} face plate opened')

    def open(
        self,
        left: float | None = None,
        top: float | None = None,
        right: float | None = None,
        bottom: float | None = None,
    ) -> None:
        # Store the clicked element's bounding rect so the placement
        # mixin can pin the modal beside the controller card.
        if left is not None and top is not None:
            self._last_click_rect = {
                'left': float(left),
                'top': float(top),
                'right': float(right) if right is not None else float(left),
                'bottom': float(bottom) if bottom is not None else float(top),
            }
        else:
            self._last_click_rect = None

        self.refresh_modal_values(force_op_refresh=True)
        self.dialog_is_open = True
        self._set_active(True)

        self.dialog.open()
        try:
            from app.hub.data_logger import write_audit_log

            write_audit_log(
                getattr(self.store, 'case_slug', 'sthr'),
                f'Opened Controller Modal for {self.controller_tag}',
                bridge=getattr(self.store, 'bridge', None),
            )
        except Exception:
            pass

    def handle_svg_click(self, e) -> None:
        target_id = None
        left = None
        top = None
        right = None
        bottom = None

        if hasattr(e, 'args') and isinstance(e.args, dict):
            target_id = e.args.get('target_id')
            left = e.args.get('left')
            top = e.args.get('top')
            right = e.args.get('right')
            bottom = e.args.get('bottom')

        if not target_id:
            return

        try:
            controller_map = getattr(self.html_element, 'controller_modals', None)
        except Exception:
            controller_map = None

        if isinstance(controller_map, dict):
            modal = controller_map.get(target_id)
            if not modal:
                modal = controller_map.get(target_id.lower())
            if modal:
                try:
                    modal.open(left=left, top=top, right=right, bottom=bottom)
                except Exception:
                    if target_id.lower() == self.controller_svg_id:
                        self.open(left=left, top=top, right=right, bottom=bottom)
                return

        if target_id.lower() == self.controller_svg_id:
            self.open(left=left, top=top, right=right, bottom=bottom)
