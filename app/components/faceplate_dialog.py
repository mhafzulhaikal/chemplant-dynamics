# app/components/faceplate_dialog.py

"""Faceplate — dialog-based, draggable, resizable, minimizable.

The original faceplate was a *right-side drawer* built from raw
``<aside class="pid-right-drawer">`` + CSS class toggling via
``ui.run_javascript``. This module replaces that approach with a
proper :class:`ui.dialog` (via the
:class:`app.components.floating_window.DraggableCard` helper)
that mirrors the Runtime Manager dialog's affordances:

* **Draggable** — pointer-event drag on the card header.
* **Resizable** — 8 invisible JS handles (N/E/S/W + NE/SE/SW/NW).
* **Minimizable** — the operator can collapse the body to a
  header strip (the same affordance the runtime manager offers
  when an operator "shelves" a faceplate).
* **Position + size persisted** to ``sessionStorage`` per case,
  so the operator's preferred placement survives close / reopen
  and tab switches.

The body content (tag/title header, mode badge, operational +
tuning inputs, Apply button, three vertical bargraphs) is the
same UI as the legacy drawer — only the host changed. The
content is wrapped in a card with class
``faceplate-dialog-card`` so the DraggableCard JS finders can
locate it across Quasar DOM swaps. The card's header row (tag +
title + mode badge + close + minimize buttons) is the drag
handle, marked with class ``faceplate-dialog-header``.

Backward-compatibility surface
------------------------------

* :class:`FaceplateDialog` exposes the same public methods the
  legacy :class:`app.components.faceplate.FaceplatePanel` did:
  ``register_modal``, ``open_for``, ``close``, ``refresh``,
  ``set_drawer`` (now a no-op — there is no drawer to attach to).
* :class:`FaceplateSpec` is re-exported from
  :mod:`app.components.faceplate` so existing imports
  (``from app.components.faceplate import FaceplateSpec``) keep
  working — the legacy module becomes a thin re-export + spec
  helper.

The dialog is constructed lazily: ``__init__`` does not create
the ``ui.dialog``; the host page calls :meth:`build` after
registering all modals so the body has a full set of
``_modals`` / ``_specs`` to draw from on first ``open_for``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from app.components.faceplate import FaceplateSpec, infer_faceplate_spec
from app.components.floating_window import DraggableCard
from app.hub.input_focus_tracker import (
    attach_focus_tracker,
    is_user_editing,
)

# CSS classes the DraggableCard JS uses to find the card and
# header. Keeping them as module-level constants so the CSS in
# ``app/static/css/faceplate.css`` (or wherever the new
# faceplate styles land) can target them by name.
CARD_CLASS = 'faceplate-dialog-card'
HEADER_CLASS = 'faceplate-dialog-header'


@dataclass(frozen=True)
class FaceplateDialogConfig:
    """Static config for a single per-page :class:`FaceplateDialog`.

    ``case_slug`` is used to scope the drag/resize persistence keys in
    ``sessionStorage`` so two open control panels (e.g. sthr + biodiesel
    in two tabs) don't clobber each other.

    ``on_close`` and ``on_minimize`` are forwarded from the runtime
    manager pattern — they let the host subscribe to dialog lifecycle
    events without subclassing.
    """

    case_slug: str
    bridge: Any | None = None
    on_close: Callable[[], None] | None = None
    on_minimize: Callable[[], None] | None = None


class FaceplateDialog:
    """Floating, draggable faceplate dialog for one case page.

    The dialog is constructed lazily by :meth:`build`; the host page
    calls ``build()`` after constructing this instance and then opens it
    on demand via :meth:`open_for`.
    """

    def __init__(self, config: FaceplateDialogConfig) -> None:
        self._case_slug = str(config.case_slug)
        self._bridge = config.bridge
        self._on_close = config.on_close
        self._on_minimize = config.on_minimize

        # tag (uppercase) -> modal instance
        self._modals: dict[str, Any] = {}
        # tag -> FaceplateSpec
        self._specs: dict[str, FaceplateSpec] = {}
        # Currently displayed tag, or None when dialog is closed
        self._active_tag: str | None = None

        # DOM element handles rebuilt every time the active
        # tag changes. The list mirrors the legacy
        # FaceplatePanel — all of these are populated by
        # :meth:`_render_body` and updated by :meth:`refresh`.
        self._tag_label: ui.label | None = None
        self._title_label: ui.label | None = None
        self._mode_badge: ui.label | None = None
        self._status_dot: ui.element | None = None

        # Three bargraphs (PV, SP, OP)
        self._pv_fill: ui.element | None = None
        self._pv_value: ui.label | None = None
        self._pv_marker: ui.element | None = None
        self._sp_fill: ui.element | None = None
        self._sp_value: ui.label | None = None
        self._op_fill: ui.element | None = None
        self._op_value: ui.label | None = None

        # Direct references to the bargraph columns (used to
        # hide SP/OP for read-only indicators without
        # traversing the DOM via ``parent_element``).
        self._pv_col: ui.column | None = None
        self._sp_col: ui.column | None = None
        self._op_col: ui.column | None = None

        # Live value label below the bargraphs
        self._pv_unit_label: ui.label | None = None
        self._sp_unit_label: ui.label | None = None
        self._op_unit_label: ui.label | None = None

        # Extended controls
        self._mode_select: ui.select | None = None
        self._sp_input: ui.number | None = None
        self._sp_input_unit: ui.label | None = None
        self._pv_input: ui.number | None = None
        self._pv_input_unit: ui.label | None = None
        self._op_input: ui.number | None = None
        self._op_input_unit: ui.label | None = None
        self._kc_input: ui.number | None = None
        self._kc_input_unit: ui.label | None = None
        self._taui_input: ui.number | None = None
        self._taui_input_unit: ui.label | None = None
        self._taud_input: ui.number | None = None
        self._taud_input_unit: ui.label | None = None
        self._apply_btn: ui.button | None = None

        # Row containers for sections (hidden when irrelevant)
        self._op_row: Any | None = None
        self._tuning_section: Any | None = None
        self._bars_row: ui.element | None = None

        # The DraggableCard helper is constructed here; the
        # actual ``ui.dialog`` is built in :meth:`build`.
        self._card = DraggableCard(
            case_slug=self._case_slug,
            card_class=CARD_CLASS,
            header_class=HEADER_CLASS,
            install_resize_handles=True,
            min_width=320,
            min_height=360,
            position_storage_key=f'faceplateDialog:{self._case_slug}',
            size_storage_key=f'faceplateDialogSize:{self._case_slug}',
            drawer_offset_var='--faceplate-drawer-offset',
        )

    # Registration

    def register_modal(
        self,
        modal: Any,
        *,
        spec: FaceplateSpec | None = None,
    ) -> None:
        """Register a controller/indicator modal with the dialog.

        Mirrors the legacy :class:`FaceplatePanel.register_modal` so
        existing call sites don't need to change. If ``spec`` is not
        provided, the dialog infers a default :class:`FaceplateSpec`
        from the modal's public attributes (``controller_tag``,
        ``pv_unit``, ``mv_unit``, ``param_keys``, ``has_tuning``,
        ``supports_operator_output``).
        """
        tag = str(getattr(modal, 'controller_tag', '')).strip().upper()
        if not tag:
            return
        self._modals[tag] = modal
        if spec is not None:
            self._specs[tag] = spec
        else:
            registry = None
            try:
                registry = modal.store._hub.registry
            except AttributeError:
                pass
            self._specs[tag] = infer_faceplate_spec(modal, registry=registry)

    # Build

    def build(self) -> FaceplateDialog:
        """Build the dialog (idempotent within an instance).

        Emits the faceplate body inside a card with class
        ``faceplate-dialog-card`` so the DraggableCard JS
        finders can locate it across Quasar DOM swaps.
        """
        self._card.build(self._build_body)
        return self

    def _build_body(self, card: DraggableCard) -> None:
        """Render the faceplate body (called by DraggableCard.build).

        Layout (top → bottom):

        ┌─ Header (tag, title, mode badge, minimize, close) ─┐ ├─
        Operational Parameters (Mode/SP/PV/OP) ───────────┤ ├─
        Controller Parameters (Kc/τI/τD) ─────────────────┤ ├─ Apply
        button ─────────────────────────────────────┤ ├─ Separator
        ────────────────────────────────────────┤ └─ Three small
        vertical bargraphs (PV/SP/OP) ────────┘
        """
        with ui.card().classes(
            f'w-full faceplate-root {CARD_CLASS}',
        ):
            # Header — tag, title, mode badge, minimize + close.
            # This row is the drag handle; the class must match
            # the DraggableCard's ``header_class`` config.
            with ui.row().classes(
                f'faceplate-header {HEADER_CLASS} no-wrap',
            ):
                with ui.column().classes('faceplate-header-text'):
                    self._tag_label = ui.label('—').classes('faceplate-tag')
                    self._title_label = ui.label(
                        'Select a controller',
                    ).classes('faceplate-title')
                with ui.row().classes(
                    'faceplate-header-right no-wrap',
                ):
                    with ui.row().classes('faceplate-mode-badge'):
                        self._status_dot = ui.element('span').classes(
                            'faceplate-status-dot faceplate-status-auto',
                        )
                        self._mode_badge = ui.label('AUTO').classes(
                            'faceplate-mode-text',
                        )
                    # Minimize button. The runtime manager's
                    # DraggableCard registration tuple convention
                    # keeps icon + tooltip in lockstep.
                    minimize_btn = (
                        ui.button(
                            icon='horizontal_rule',
                            color=None,
                        )
                        .props('flat round dense size=sm')
                        .classes('faceplate-minimize-btn')
                    )
                    minimize_btn.on(
                        'click',
                        lambda _, c=card: (
                            c.toggle_minimize(),
                            self._on_minimize() if self._on_minimize else None,
                        ),
                    )
                    minimize_tooltip = ui.tooltip('Minimize')
                    card.register_minimize_button(
                        minimize_btn,
                        minimize_tooltip,
                    )
                    ui.button(
                        icon='close',
                        color=None,
                    ).props('flat round dense size=sm').classes(
                        'faceplate-close-btn',
                    ).on(
                        'click',
                        lambda _: (
                            self.close(),
                            self._on_close() if self._on_close else None,
                        ),
                    )

            # Body wrapper
            with ui.element('div').classes('faceplate-body'):
                # Extended controls — operational parameters.
                with ui.column().classes('faceplate-section faceplate-op-section'):
                    self._op_section_title = ui.label('Operational Parameters').classes(
                        'faceplate-section-title',
                    )
                    self._mode_row = ui.element('div').classes('faceplate-input-row')
                    with self._mode_row:
                        ui.label('Mode').classes('faceplate-input-label')
                        self._mode_select = (
                            ui.select(
                                options={
                                    'off': 'Off',
                                    'manual': 'Manual',
                                    'auto': 'Automatic',
                                },
                                value='auto',
                            )
                            .props(
                                'dense borderless popup-content-class="faceplate-mode-popup"',
                            )
                            .classes(
                                'faceplate-input-field faceplate-mode-select',
                            )
                        )
                        self._mode_select.on_value_change(self._on_mode_change)
                        ui.label('').classes('faceplate-input-unit')

                    self._sp_row = ui.element('div').classes('faceplate-input-row')
                    with self._sp_row:
                        ui.label('SP').classes('faceplate-input-label')
                        self._sp_input = self._build_input(
                            'SP',
                            0.0,
                            1000.0,
                            0.01,
                            field_name='SP',
                        )
                        self._sp_input_unit = ui.label('').classes(
                            'faceplate-input-unit faceplate-input-unit-sp',
                        )

                    with ui.element('div').classes('faceplate-input-row'):
                        ui.label('PV').classes('faceplate-input-label')
                        self._pv_input = self._build_input(
                            'PV',
                            0.0,
                            1000.0,
                            0.01,
                            readonly=False,
                            field_name='PV',
                        )
                        self._pv_input_unit = ui.label('').classes(
                            'faceplate-input-unit faceplate-input-unit-pv',
                        )

                    self._op_row = ui.element('div').classes(
                        'faceplate-input-row',
                    )
                    with self._op_row:
                        ui.label('OP').classes('faceplate-input-label')
                        self._op_input = self._build_input(
                            'OP',
                            0.0,
                            100.0,
                            0.01,
                            field_name='OP',
                        )
                        self._op_input_unit = ui.label('').classes(
                            'faceplate-input-unit faceplate-input-unit-op',
                        )

                # Extended controls — tuning.
                self._tuning_section = ui.column().classes(
                    'faceplate-section',
                )
                with self._tuning_section:
                    ui.label('Controller Parameters').classes(
                        'faceplate-section-title',
                    )
                    with ui.element('div').classes('faceplate-input-row'):
                        ui.label('Kc').classes('faceplate-input-label')
                        self._kc_input = self._build_input(
                            'Kc',
                            0.0,
                            50.0,
                            0.01,
                            field_name='Kc',
                        )
                        self._kc_input_unit = ui.label('%CO/%TO').classes('faceplate-input-unit')
                    with ui.element('div').classes('faceplate-input-row'):
                        ui.label('tauI').classes('faceplate-input-label')
                        self._taui_input = self._build_input(
                            'tauI',
                            0.01,
                            100.0,
                            0.01,
                            field_name='tauI',
                        )
                        self._taui_input_unit = ui.label('min').classes('faceplate-input-unit')
                    with ui.element('div').classes('faceplate-input-row'):
                        ui.label('tauD').classes('faceplate-input-label')
                        self._taud_input = self._build_input(
                            'tauD',
                            0.0,
                            50.0,
                            0.01,
                            field_name='tauD',
                        )
                        self._taud_input_unit = ui.label('min').classes('faceplate-input-unit')

                # Apply button.
                self._apply_btn = (
                    ui.button(
                        'Apply',
                        color=None,
                    )
                    .props('flat dense')
                    .classes('faceplate-apply-btn')
                )
                self._apply_btn.on('click', self._on_apply)

                ui.separator().classes('faceplate-section-separator')

                # Vertical bargraphs.
                self._bars_row = ui.element('div').classes(
                    'faceplate-bars faceplate-bars-3',
                )
                with self._bars_row:
                    self._pv_col = ui.column().classes('faceplate-bar-col items-center text-center')
                    with self._pv_col:
                        ui.label('PV').classes(
                            'faceplate-bar-label faceplate-bar-label-pv',
                        )
                        with ui.element('div').classes('faceplate-bar-track'):
                            self._pv_fill = ui.element('div').classes(
                                'faceplate-bar-fill faceplate-bar-fill-pv',
                            )
                            self._pv_marker = ui.element('div').classes('faceplate-bar-sp-marker')
                        self._pv_value = ui.label('—').classes(
                            'faceplate-bar-value',
                        )
                        self._pv_unit_label = ui.label('').classes(
                            'faceplate-bar-unit',
                        )

                    self._sp_col = ui.column().classes('faceplate-bar-col items-center text-center')
                    with self._sp_col:
                        ui.label('SP').classes(
                            'faceplate-bar-label faceplate-bar-label-sp',
                        )
                        with ui.element('div').classes('faceplate-bar-track'):
                            self._sp_fill = ui.element('div').classes(
                                'faceplate-bar-fill faceplate-bar-fill-sp',
                            )
                        self._sp_value = ui.label('—').classes(
                            'faceplate-bar-value',
                        )
                        self._sp_unit_label = ui.label('').classes(
                            'faceplate-bar-unit',
                        )

                    self._op_col = ui.column().classes('faceplate-bar-col items-center text-center')
                    with self._op_col:
                        ui.label('OP').classes(
                            'faceplate-bar-label faceplate-bar-label-op',
                        )
                        with ui.element('div').classes('faceplate-bar-track'):
                            self._op_fill = ui.element('div').classes(
                                'faceplate-bar-fill faceplate-bar-fill-op',
                            )
                        self._op_value = ui.label('—').classes(
                            'faceplate-bar-value',
                        )
                        self._op_unit_label = ui.label('').classes(
                            'faceplate-bar-unit',
                        )

                # Initial placeholder.
                self._set_bar(self._pv_fill, 0.0)
                self._set_bar(self._sp_fill, 0.0)
                self._set_bar(self._op_fill, 0.0)

            # Footer / Status bar
            with ui.element('div').classes('faceplate-statusbar'):
                with ui.element('div').classes('faceplate-statusbar-cell'):
                    ui.label('STEP').classes('faceplate-statusbar-cell-label')
                    self._step_label = ui.label('—').classes(
                        'faceplate-statusbar-cell-value',
                    )
                with ui.element('div').classes('faceplate-statusbar-cell'):
                    ui.label('SIM TIME').classes('faceplate-statusbar-cell-label')
                    self._sim_time_label = ui.label('—').classes(
                        'faceplate-statusbar-cell-value',
                    )
                    try:
                        from gateway.registry.config_registry import get_case_config

                        case_cfg = get_case_config(self._case_slug)
                        self._case_default_unit = getattr(case_cfg, 'DEFAULT_TIME_UNIT', 'min')
                        self._from_minutes = getattr(
                            case_cfg, 'from_minutes', lambda val, unit: val
                        )
                    except Exception:
                        self._case_default_unit = 'min'
                        self._from_minutes = lambda val, unit: val
                with ui.element('div').classes('faceplate-statusbar-cell'):
                    ui.label('MODE').classes('faceplate-statusbar-cell-label')
                    self._mode_footer_label = ui.label('—').classes(
                        'faceplate-statusbar-cell-value'
                    )

                # We place the resize handle as a decorative item at the
                # very right
                # The actual resize handles are absolute positioned, so this
                # just ensures spacing
                with ui.element('div').classes('faceplate-statusbar-cell min-w-[16px] min-h-[8px]'):
                    pass

    # Public API — mirrors FaceplatePanel

    def open_for(self, tag: str) -> None:
        """Open (or refocus) the faceplate on ``tag``."""
        tag = str(tag).strip().upper()
        if tag not in self._modals:
            return
        self._active_tag = tag
        self._rebuild_active_body()
        self._card.open()
        try:
            from app.hub.data_logger import write_audit_log

            write_audit_log(self._case_slug, f'Opened Faceplate for {tag}')
        except Exception:
            pass
        # Pull the latest values from the modal's store
        self.refresh()

    def close(self) -> None:
        """Close the faceplate dialog."""
        tag = self._active_tag
        self._active_tag = None
        self._card.close()
        if tag:
            try:
                from app.hub.data_logger import write_audit_log

                write_audit_log(self._case_slug, f'Closed Faceplate for {tag}')
            except Exception:
                pass

    def toggle(self) -> None:
        """Open the dialog if hidden, close it if visible."""
        self._card.toggle()

    @property
    def card(self) -> DraggableCard:
        """The underlying DraggableCard helper (for testing)."""
        return self._card

    def set_drawer(self, drawer: Any) -> None:
        """No-op kept for backward compatibility with FaceplatePanel.

        The dialog is hosted in a Quasar ``<q-dialog>`` portal, not a
        page aside, so there is no drawer element to attach to. The
        argument is accepted but ignored.
        """
        del drawer  # explicitly unused

    # Live refresh — called by the page's live flusher

    def refresh(self) -> None:
        """Update bargraph fills, numeric labels, and the SP marker.

        Safe to call when the dialog is closed (no-op) or when no tag is
        active (no-op). Mirrors the legacy
        :class:`FaceplatePanel.refresh` exactly so the
        :class:`app.hub.children.FaceplateChild` can drive either
        implementation.
        """
        if not self._active_tag:
            return
        if self._pv_fill is None or self._sp_fill is None or self._op_fill is None:
            return

        modal = self._modals.get(self._active_tag)
        spec = self._specs.get(self._active_tag)
        if modal is None or spec is None:
            return

        # Dynamically trigger rebuild if modal type has changed (e.g. FI-100
        # switching editable state)
        if hasattr(modal, 'modal_type') and modal.modal_type is not None:
            from app.components.faceplate import ModalType

            try:
                if spec.modal_type != ModalType(modal.modal_type):
                    self._rebuild_active_body()
            except ValueError:
                pass

        # Post-reset input-push suppression. The live flusher
        # sets ``_suppress_input_push`` on this dialog for one
        # tick after an engine reset. We still repaint the
        # bargraphs and SP marker (those reflect simulation
        # state, not operator input) but skip the
        # store→input write below so the operator's last-typed
        # numeric values stay on screen.
        suppress = bool(getattr(self, '_suppress_input_push', False))

        # PV
        pv = self._read_field(modal, 'pv', fallback=spec.pv_min)
        pv_pct = self._to_percent(pv, spec.pv_min, spec.pv_max)
        self._set_bar(self._pv_fill, pv_pct)
        if self._pv_value is not None:
            self._pv_value.set_text(self._fmt(pv, spec.pv_decimals))
        if self._pv_marker is not None:
            sp = self._read_field(modal, 'sp', fallback=spec.sp_min)
            sp_pct = self._to_percent(sp, spec.pv_min, spec.pv_max)
            self._set_marker(self._pv_marker, sp_pct)

        # Update status bar manually in case bindings fail or pause
        if self._bridge and hasattr(self._bridge, 'state'):
            state = self._bridge.state
            if getattr(self, '_step_label', None):
                t_val = getattr(state, 'tick', None)
                self._step_label.set_text(f'{int(t_val) if t_val is not None else 0:>6d}')
            if getattr(self, '_sim_time_label', None):
                time_val = getattr(state, 'last_sim_time', None)
                try:
                    f_min = getattr(self, '_from_minutes', lambda val, unit: val)
                    unit = getattr(self, '_case_default_unit', 'min')
                    time_num = float(time_val) if time_val is not None else 0.0
                    self._sim_time_label.set_text(f'{f_min(time_num, unit):.2f} {unit}')
                except Exception:
                    pass

        # SP
        sp = self._read_field(modal, 'sp', fallback=spec.sp_min)

        # Color the PV text (bargraph label)
        if self._pv_value is not None:
            diff = abs(pv - sp)
            if diff > 0.05 * abs(sp):
                self._pv_value.classes(add='pv-danger', remove='pv-warning')
            elif diff > 0.01 * abs(sp):
                self._pv_value.classes(add='pv-warning', remove='pv-danger')
            else:
                self._pv_value.classes(remove='pv-warning pv-danger')

        # SP
        if spec.show_sp_bar:
            sp = self._read_field(modal, 'sp', fallback=spec.sp_min)
            sp_pct = self._to_percent(sp, spec.sp_min, spec.sp_max)
            self._set_bar(self._sp_fill, sp_pct)
            if self._sp_value is not None:
                self._sp_value.set_text(self._fmt(sp, spec.sp_decimals))

        # OP
        if spec.show_op_bar:
            op = self._read_field(modal, 'op', fallback=spec.op_min)
            op_pct = self._to_percent(op, spec.op_min, spec.op_max)
            self._set_bar(self._op_fill, op_pct)
            if self._op_value is not None:
                self._op_value.set_text(self._fmt(op, spec.op_decimals))

        # Mode badge.
        try:
            status = modal._selected_status() if hasattr(modal, '_selected_status') else 'auto'
        except Exception:
            status = 'auto'

        if self._mode_badge is not None:
            abbr_map = {'auto': 'AUTO', 'manual': 'MAN', 'off': 'OFF'}
            display_text = abbr_map.get(status, status.upper())
            self._mode_badge.set_text(display_text)
            if self._status_dot is not None:
                cls_map = {
                    'off': 'faceplate-status-off',
                    'manual': 'faceplate-status-manual',
                    'auto': 'faceplate-status-auto',
                }
                for cls in cls_map.values():
                    self._status_dot.classes(remove=cls)
                self._status_dot.classes(
                    add=cls_map.get(status, 'faceplate-status-auto'),
                )

            if getattr(self, '_mode_footer_label', None) is not None:
                self._mode_footer_label.set_text(display_text)

        # Readonly state — keep the dialog inputs in lockstep
        # with the modal's per-mode readonly map.
        try:
            ro_map = modal.read_only_map(status) if hasattr(modal, 'read_only_map') else None
        except Exception:
            ro_map = None
        if ro_map:
            self._apply_readonly_map(ro_map, spec)

        if not suppress:
            self._sync_input_from_store(
                self._sp_input,
                'sp',
                self._read_field(modal, 'sp', fallback=spec.sp_min),
                decimals=spec.sp_decimals,
            )
            self._sync_input_from_store(
                self._pv_input,
                'pv',
                self._read_field(modal, 'pv', fallback=spec.pv_min),
                decimals=spec.pv_decimals,
            )

            # Color the PV input field
            if self._pv_input is not None:
                diff = abs(pv - sp)
                if diff > 0.05 * abs(sp):
                    self._pv_input.classes(add='pv-danger', remove='pv-warning')
                elif diff > 0.01 * abs(sp):
                    self._pv_input.classes(add='pv-warning', remove='pv-danger')
                else:
                    self._pv_input.classes(remove='pv-warning pv-danger')
            # In manual mode the operator controls OP directly —
            # don't overwrite their input field (mirrors the modal
            # guard in base.py refresh_modal_values).
            if spec.show_op_bar and self._op_input is not None:
                if status != 'manual':
                    self._sync_input_from_store(
                        self._op_input,
                        'op',
                        self._read_field(modal, 'op', fallback=spec.op_min),
                        decimals=spec.op_decimals,
                    )
            self._sync_input_from_store(
                self._kc_input,
                'kc',
                self._read_field(modal, 'kc', fallback=0.0),
                decimals=2,
            )

            self._sync_input_from_store(
                self._taui_input,
                'tau_i',
                self._read_field(modal, 'tau_i', fallback=0.0),
                decimals=2,
            )
            self._sync_input_from_store(
                self._taud_input,
                'tau_d',
                self._read_field(modal, 'tau_d', fallback=0.0),
                decimals=2,
            )

    # Body rebuild — re-renders tag-specific sections when the
    # active tag changes.

    def _rebuild_active_body(self) -> None:
        tag = self._active_tag
        if not tag:
            return
        modal = self._modals.get(tag)
        spec = self._specs.get(tag)
        if modal is None or spec is None:
            return

        # Dynamically refresh modal_type if the modal supports changing it
        if hasattr(modal, 'modal_type') and modal.modal_type is not None:
            from app.components.faceplate import ModalType

            try:
                new_type = ModalType(modal.modal_type)
                if spec.modal_type != new_type:
                    from dataclasses import replace

                    new_show_sp = bool(spec.has_tuning) or new_type == ModalType.CONTROLLER
                    spec = replace(spec, modal_type=new_type, show_sp_bar=new_show_sp)
                    self._specs[tag] = spec
            except ValueError:
                pass

        def _update_bounds(inp, mn, mx, st):
            if inp is not None:
                inp.min = mn
                inp.max = mx
                inp._props['step'] = st
                inp.update()

        _update_bounds(self._sp_input, spec.sp_min, spec.sp_max, spec.sp_step)
        _update_bounds(self._pv_input, spec.pv_min, spec.pv_max, spec.pv_step)
        _update_bounds(self._op_input, spec.op_min, spec.op_max, spec.op_step)
        _update_bounds(self._kc_input, spec.kc_min, spec.kc_max, spec.kc_step)
        _update_bounds(self._taui_input, spec.taui_min, spec.taui_max, spec.taui_step)
        _update_bounds(self._taud_input, spec.taud_min, spec.taud_max, spec.taud_step)

        # Header
        if self._tag_label is not None:
            self._tag_label.set_text(spec.tag)
        if self._title_label is not None:
            self._title_label.set_text(spec.title)
        if self._pv_unit_label is not None:
            self._pv_unit_label.set_text(spec.pv_unit)
        if self._sp_unit_label is not None:
            self._sp_unit_label.set_text(spec.sp_unit)
        if self._op_unit_label is not None:
            self._op_unit_label.set_text(spec.op_unit)

        # Input row unit updates
        if self._pv_input_unit is not None:
            self._pv_input_unit.set_text(spec.pv_unit)
        if self._sp_input_unit is not None:
            self._sp_input_unit.set_text(spec.sp_unit)
        if self._op_input_unit is not None:
            self._op_input_unit.set_text(spec.op_unit)

        # Tuning row unit updates
        if self._kc_input_unit is not None:
            # Use getattr(modal, 'kc_unit') but actually we need to call
            # it if it's a property or method
            # Wait, in base.py, `kc_unit` is a property:
            # `@property \n def kc_unit(self) -> str:`
            # So `getattr(modal, 'kc_unit')` gets the string value.
            self._kc_input_unit.set_text(getattr(modal, 'kc_unit', '%CO/%TO'))
        if self._taui_input_unit is not None:
            self._taui_input_unit.set_text(getattr(modal, 'taui_unit', 'min'))
        if self._taud_input_unit is not None:
            self._taud_input_unit.set_text(getattr(modal, 'taud_unit', 'min'))

        # SP / OP bargraph visibility
        if self._sp_col is not None:
            self._sp_col.set_visibility(spec.show_sp_bar)
        if self._op_col is not None:
            self._op_col.set_visibility(spec.show_op_bar)
        if self._bars_row is not None:
            visible_count = (1 if spec.show_sp_bar else 0) + (1 if spec.show_op_bar else 0) + 1
            try:
                self._bars_row.classes(
                    remove='faceplate-bars-1 faceplate-bars-3',
                )
                self._bars_row.classes(
                    add=('faceplate-bars-3' if visible_count == 3 else 'faceplate-bars-1'),
                )
            except Exception:
                pass

        # Extended controls
        if self._mode_select is not None:
            mode_value = 'auto'
            try:
                mode_value = modal._selected_status()
            except Exception:
                pass
            self._mode_select.value = mode_value
            self._mode_select.set_visibility(spec.has_mode)

        for inp, ui_key, default, d in (
            (self._sp_input, 'sp', spec.sp_min, spec.sp_decimals),
            (self._pv_input, 'pv', spec.pv_min, spec.pv_decimals),
            (self._op_input, 'op', spec.op_min, spec.op_decimals),
            (self._kc_input, 'kc', 0.0, 2),
            (self._taui_input, 'tau_i', 0.0, 2),
            (self._taud_input, 'tau_d', 0.0, 2),
        ):
            if inp is None:
                continue
            try:
                val = modal._default_value(ui_key, default)
            except Exception:
                val = default
            try:
                val = float(val)
            except (ValueError, TypeError):
                val = float(default)

            # SKILL.md Rule 13 (Amended): Enforce formats ONLY for readonly
            # fields
            if hasattr(inp, '_props'):
                if inp._props.get('readonly'):
                    inp.format = f'%.{d}f'
                    try:
                        val = round(float(val), d)
                    except (TypeError, ValueError):
                        pass
                else:
                    inp.format = None
                inp.update()

            inp.value = val

        from app.components.faceplate import ModalType

        is_indicator_readonly = spec.modal_type in (
            ModalType.INDICATOR_READONLY,
            ModalType.VALVE_POSITION,
        )
        is_editable = spec.modal_type == ModalType.INDICATOR_EDITABLE
        is_controller = spec.modal_type == ModalType.CONTROLLER

        if self._pv_input is not None:
            if is_controller:
                self._set_field_readonly(self._pv_input, True)
            else:
                self._set_field_readonly(self._pv_input, not is_editable)

        if getattr(self, '_op_section_title', None) is not None:
            self._op_section_title.set_visibility(not is_indicator_readonly)
        if getattr(self, '_mode_row', None) is not None:
            self._mode_row.set_visibility(is_controller and spec.has_mode)
        if getattr(self, '_sp_row', None) is not None:
            self._sp_row.set_visibility(is_controller)
        if self._op_row is not None:
            self._op_row.set_visibility(is_controller and spec.has_op)
        if self._tuning_section is not None:
            self._tuning_section.set_visibility(is_controller and spec.has_tuning)
        if self._apply_btn is not None:
            self._apply_btn.set_visibility(is_controller)

    # Internal helpers

    def _build_input(
        self,
        name: str,
        min_value: float,
        max_value: float,
        step: float,
        *,
        readonly: bool = False,
        field_name: str | None = None,
    ) -> ui.number:
        """Build a small numeric input matching the faceplate's row grid."""
        field = (
            ui.number(value=0.0, min=min_value, max=max_value, step=step)
            .props(
                'dense color="amber"'
                + (' readonly' if readonly else '')
                + (
                    f' tooltip="Press Enter or click Apply to commit {name}"'
                    if not readonly
                    else ''
                ),
            )
            .classes('faceplate-input-field')
        )

        attach_focus_tracker(field)

        if field_name and not readonly:
            modal_field = field_name

            def _commit(_=None, fld=field, m_field=modal_field):
                modal = None
                if self._active_tag:
                    modal = self._modals.get(self._active_tag)
                if modal is None:
                    return
                apply = getattr(modal, '_apply_numeric_value', None)
                if callable(apply):
                    try:
                        apply(m_field, fld)
                    except Exception:
                        pass

            for evt in ('blur', 'keydown.enter'):
                try:
                    field.on(evt, _commit)
                except Exception:
                    pass

        return field

    def _on_mode_change(self, _=None) -> None:
        """Route the Mode select edit into the active modal."""
        if not self._active_tag:
            return
        modal = self._modals.get(self._active_tag)
        if modal is None or self._mode_select is None:
            return
        commit = getattr(modal, 'commit_mode_change', None)
        if not callable(commit):
            return
        try:
            commit(
                str(self._mode_select.value or 'auto'),
                include_tuning=False,
            )
        except Exception:
            pass
        self.refresh()

    def _sync_input_from_store(
        self,
        field: ui.number | None,
        _key: str,
        value: Any,
        decimals: int | None = None,
    ) -> None:
        """Push a fresh store value into a dialog input.

        Skips the write if the field is currently focused (so we don't
        clobber the user's in-progress text) and skips the write if the
        value is already in sync.
        """
        if field is None:
            return

        if is_user_editing(field):
            return

        format_changed = False
        is_readonly = getattr(field, '_props', {}).get('readonly')
        if decimals is not None and is_readonly:
            new_fmt = f'%.{decimals}f'
            if getattr(field, 'format', None) != new_fmt:
                field.format = new_fmt
                # Force NiceGUI to re-evaluate _value_to_model_value
                field._value = None  # type: ignore
                format_changed = True
            if value is not None:
                try:
                    value = round(float(value), decimals)
                except (TypeError, ValueError):
                    pass
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

        if not format_changed:
            try:
                current = field.value
            except Exception:
                current = None
            try:
                if current is not None and current != '' and value is not None:
                    if float(current) == float(value):
                        return
            except (TypeError, ValueError):
                if str(current) == str(value):
                    return
        try:
            field.value = value  # type: ignore
        except Exception:
            pass

    def _set_field_readonly(
        self,
        field: Any | None,
        readonly: bool,
    ) -> None:
        """Toggle the readonly state of a dialog input."""
        if field is None:
            return
        try:
            if readonly:
                field.props('readonly')
                field.classes(add='faceplate-readonly')
            else:
                field.props(remove='readonly')
                field.classes(remove='faceplate-readonly')
                if hasattr(field, 'format'):
                    field.format = None
                if hasattr(field, '_props'):
                    field._props.pop('format', None)
                if hasattr(field, 'update'):
                    field.update()
        except Exception:
            pass

    def _apply_readonly_map(
        self,
        ro_map: dict[str, bool],
        spec: FaceplateSpec,
    ) -> None:
        """Apply the modal's per-mode readonly flags to dialog inputs."""
        if self._mode_select is not None:
            self._set_field_readonly(
                self._mode_select,
                bool(ro_map.get('mode', False)),
            )

        self._set_field_readonly(
            self._sp_input,
            bool(ro_map.get('sp', True)) if spec.show_sp_bar else True,
        )
        self._set_field_readonly(
            self._pv_input,
            bool(ro_map.get('pv', True)),
        )
        if self._op_input is not None and spec.has_op:
            self._set_field_readonly(
                self._op_input,
                bool(ro_map.get('op', True)),
            )

        if spec.has_tuning:
            self._set_field_readonly(
                self._kc_input,
                bool(ro_map.get('kc', True)),
            )
            self._set_field_readonly(
                self._taui_input,
                bool(ro_map.get('tau_i', True)),
            )
            self._set_field_readonly(
                self._taud_input,
                bool(ro_map.get('tau_d', True)),
            )

    def _on_apply(self) -> None:
        """Apply the faceplate's edits to the active modal."""
        if not self._active_tag:
            return
        modal = self._modals.get(self._active_tag)
        if modal is None:
            return

        field_map = {
            'sp': (self._sp_input, 'SP'),
            'pv': (self._pv_input, 'PV'),
            'op': (self._op_input, 'OP'),
            'kc': (self._kc_input, 'Kc'),
            'tau_i': (self._taui_input, 'tauI'),
            'tau_d': (self._taud_input, 'tauD'),
        }
        for _ui_key, (field, modal_field) in field_map.items():
            if field is None:
                continue
            try:
                apply = getattr(modal, '_apply_numeric_value', None)
                if callable(apply):
                    apply(modal_field, field)
            except Exception:
                pass

        if self._mode_select is not None and hasattr(modal, 'commit_mode_change'):
            try:
                modal.commit_mode_change(
                    str(self._mode_select.value or 'auto'),
                    include_tuning=True,
                )
            except Exception:
                pass

        try:
            modal.apply_dialog_values()
            try:
                from app.hub.data_logger import write_audit_log

                mode_str = (
                    self._mode_select.value.upper()
                    if self._mode_select and self._mode_select.value
                    else 'N/A'
                )
                write_audit_log(
                    self._case_slug, f'Applied values to {self._active_tag} (Mode: {mode_str})'
                )
            except Exception:
                pass
        except Exception:
            pass
        self.refresh()

    def _read_field(
        self,
        modal: Any,
        ui_key: str,
        *,
        fallback: float,
    ) -> float:
        """Read a numeric value from the modal's store, with fallbacks."""
        try:
            modal.refresh_modal_values(
                force_op_refresh=False,
                force_sp_refresh=False,
            )
        except Exception:
            pass
        store = getattr(modal, 'store', None)
        if store is not None and hasattr(store, 'get'):
            value_keys = getattr(modal, 'value_keys', {})
            engine_key = value_keys.get(ui_key)
            if not engine_key:
                param_keys = getattr(modal, 'param_keys', None) or {}
                if isinstance(param_keys, dict) and ui_key in param_keys:
                    engine_key = param_keys[ui_key]
            if engine_key:
                try:
                    return float(store.get(engine_key, fallback))
                except Exception:
                    pass
        if ui_key == 'pv':
            return float(getattr(modal, 'pv_default', fallback))
        return fallback

    @staticmethod
    def _to_percent(value: float, lo: float, hi: float) -> float:
        """Map a value in [lo, hi] to a [0, 100] bargraph fill height."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return 0.0
        if hi <= lo:
            return 0.0
        pct = (v - lo) / (hi - lo) * 100.0
        if pct < 0.0:
            return 0.0
        if pct > 100.0:
            return 100.0
        return pct

    @staticmethod
    def _set_bar(
        fill_element: ui.element | None,
        pct: float,
    ) -> None:
        """Drive a bargraph fill's height in % via inline style."""
        if fill_element is None:
            return
        try:
            fill_element.style(f'height: {pct:.1f}%;')
        except Exception:
            pass

    @staticmethod
    def _set_marker(
        marker_element: ui.element | None,
        pct: float,
    ) -> None:
        """Position the SP marker on the PV bargraph."""
        if marker_element is None:
            return
        try:
            marker_element.style(f'bottom: {pct:.1f}%;')
        except Exception:
            pass

    @staticmethod
    def _fmt(value: float, decimals: int) -> str:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return '—'
        return f'{round(v, decimals):.{decimals}f}'


__all__ = [
    'FaceplateDialog',
    'FaceplateDialogConfig',
    'FaceplateSpec',
    'CARD_CLASS',
    'HEADER_CLASS',
]
