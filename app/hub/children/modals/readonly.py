# app/hub/children/modals/readonly.py

"""Read-only :class:`ReadOnlyControllerModal` (indicator dialog).

Rewritten from the legacy ``app/pid/sthr/controller_modal.py`` during
the v1 purge. Same visual shell as :class:`ControllerModal` but with
only a read-only PV display and an optional description — no mode
selector, no parameter inputs, no Apply button.

Used for indicator-only controllers (FI-100, LI-100, FI-102, VP-100,
TI-100, TI-101..104, PI-100, LV-100, TV-100, FV-100..102).
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.hub.input_focus_tracker import attach_focus_tracker, is_user_editing

__all__ = ['ReadOnlyControllerModal']


class ReadOnlyControllerModal:
    """Read-only indicator modal.

    Mirrors the :class:`ControllerModal` UI shell (close button, header,
    footer with Face plate button, SVG hover / click affordance) but
    contains only a read-only PV display row and an optional role
    description. No mode, no SP, no tuning.
    """

    def __init__(
        self,
        html_element: ui.element,
        controller_tag: str,
        *,
        unit: str = '',
        description: str = '',
        pv_key: str | None = None,
        sp_key: str | None = None,
        pv_default: float = 0.0,
        title: str | None = None,
        store: Any = None,
        decimals: int = 1,
    ) -> None:
        self.html_element = html_element
        self.controller_tag = str(controller_tag).strip().upper()
        self.controller_svg_id = self.controller_tag.lower()
        self.unit = unit
        self.description = description
        self.pv_key = pv_key or f'{self.controller_svg_id.replace("-", "_")}_pv'
        self.sp_key = sp_key
        self.pv_default = float(pv_default)
        self.decimals = int(decimals)
        self.title = title or f'{self.controller_tag} — {description or "Indicator"}'
        # Optional engine-backed store. When provided the hub's
        # ``ModalChild`` per-tick refresh pulls the live PV from the
        # store and re-renders the dialog label — otherwise the
        # dialog stays at ``pv_default`` forever.
        self.store = store

        self.dialog_is_open = False

        # Optional reference to the right-drawer faceplate. Wired
        # by the host page after construction.
        self._faceplate: Any = None

        # Unique per-modal CSS class — same scheme as
        # :class:`ControllerModal`. Keeps the smart-placement JS
        # selector targeted at this modal even when several
        # read-only modals share the page.
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
                    ui.button(
                        icon='close',
                        color=None,
                        on_click=self.dialog.close,
                    ).props('flat round dense size=sm').classes(
                        'ctrl-param-close-btn',
                    )

            with ui.column().classes('ctrl-param-dialog-content'):
                self._build_readonly_section()

            with ui.row().classes('ctrl-param-footer w-full'):
                ui.button('Face plate', on_click=self.open_faceplate).props('flat dense').classes(
                    'ctrl-param-faceplate-btn'
                )
                # No Apply button — read-only

        # Bind events
        self.dialog.on('hide', self.hide_dialog)
        self._install_svg_hooks()

    # -------------------------------
    # UI builders
    # -------------------------------

    @property
    def value_keys(self) -> dict[str, str | None]:
        return {
            'pv': getattr(self, 'pv_key', None),
            'sp': getattr(self, 'sp_key', None),
            'op': None,
            'kc': None,
            'tau_i': None,
            'tau_d': None,
            'status': None,
        }

    @property
    def modal_type(self) -> str:
        if getattr(self, 'sp_key', None):
            return 'indicator_editable'
        pv_unit = getattr(self, 'unit', '')
        svg_id = getattr(self, 'controller_svg_id', '')
        if '%' in pv_unit and (
            'vp' in svg_id
            or 'valve' in svg_id
            or 'fv-' in svg_id
            or 'tv-' in svg_id
            or 'lv-' in svg_id
        ):
            return 'valve_position'
        return 'indicator_readonly'

    def _build_readonly_section(self) -> None:
        with ui.card().tight().classes('ctrl-param-section'):
            ui.label('Operational Parameters').classes('ctrl-param-section-title')
            with ui.element('div').classes('ctrl-param-inputs'):
                with ui.element('div').classes('ctrl-param-row'):
                    ui.label('PV').classes('ctrl-param-variable')
                    _fmt = f'%.{self.decimals}f'
                    _ro = '' if self.sp_key else ' readonly'
                    _props = f'dense color="amber"{_ro}'
                    self.pv_input = (
                        ui.number(
                            value=self.pv_default,
                            format=_fmt,
                        )
                        .props(_props)
                        .classes('ctrl-param-value ctrl-param-readonly-value-text')
                    )
                    attach_focus_tracker(self.pv_input)

                    def _commit_pv(_=None):
                        self._apply_numeric_value('pv', self.pv_input)

                    self.pv_input.on('keydown.enter', _commit_pv)
                    self.pv_input.on('blur', _commit_pv)

                    # Keep reference for any other usage
                    self.pv_label = self.pv_input
                    ui.label(self.unit).classes('ctrl-param-unit')

    def _apply_numeric_value(self, field_name: str, field: ui.number) -> None:
        if str(field_name).lower() != 'pv' or self.store is None:
            return
        if field.value is None:
            return
        try:
            value = float(field.value)
        except (TypeError, ValueError):
            return
        target_key = getattr(self, 'sp_key', None)
        if not target_key:
            return
        self.store.set(target_key, value)

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
                    '{self.controller_tag}: click to view indicator');

                const applyGlow = (active) => {{
                    const nodes = group.querySelectorAll('*');
                    nodes.forEach(node => {{
                        node.style.cursor = 'pointer';
                        if (node.tagName && (
                            node.tagName.toLowerCase() === 'path' ||
                            node.tagName.toLowerCase() === 'rect')) {{
                            node.style.transition = 'stroke 0.15s ease';
                            node.style.stroke = active ? '#ffd600' : '#ffffff';
                        }}
                    }});
                }};

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

    # -------------------------------
    # Event handlers
    # -------------------------------

    def hide_dialog(self) -> None:
        self.dialog_is_open = False
        self._set_active(False)

    def set_faceplate(self, faceplate: Any) -> None:
        """Attach the right-drawer faceplate to this read-only modal."""
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
        if left is not None and top is not None:
            self._last_click_rect = {
                'left': float(left),
                'top': float(top),
                'right': float(right) if right is not None else float(left),
                'bottom': float(bottom) if bottom is not None else float(top),
            }
        else:
            self._last_click_rect = None

        # Refresh + mark active BEFORE opening so the operator
        # sees the freshest live value (from the hub store, not
        # pv_default) and the SVG hover glow flips to "active"
        # on the first paint — same ordering as
        # :meth:`ControllerModal.open`.
        self.refresh_modal_values()
        self.dialog_is_open = True
        self._set_active(True)
        self.dialog.open()

    def refresh_value(self, value: float | None = None) -> None:
        """Update the live value shown in the dialog."""
        if value is None:
            value = self.pv_default
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = self.pv_default

        if isinstance(value, float):
            pass
        else:
            pass

        if getattr(self, 'pv_input', None) and is_user_editing(self.pv_input):
            return

        self.pv_input.value = value
        self.pv_input.update()

    def refresh_modal_values(
        self,
        force_op_refresh: bool = False,
        force_sp_refresh: bool = False,
    ) -> None:
        """Hub-side hook — mirror the snapshot into the open dialog.

        :class:`ModalChild` calls this every tick on every modal that
        reports ``dialog_is_open=True``. Read-only modals have no
        SP/PV/OP inputs to mirror, so the only thing that needs to
        update is the live PV label.

        The value is read from ``self.store`` when a store is available
        (engine-backed path); otherwise we fall back to ``pv_default``
        so pure-UI mode still renders sensibly.
        """
        if not getattr(self, 'dialog_is_open', False):
            return

        if getattr(self, 'store', None) is not None:
            try:
                live = self.store.get(self.pv_key, self.pv_default)
            except Exception:
                live = self.pv_default
        else:
            live = self.pv_default

        self.refresh_value(value=live)

    def handle_svg_click(self, e) -> None:
        """Click handler for the shared click emitter on the html element."""
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

        if target_id.lower() != self.controller_svg_id:
            return

        self.open(left=left, top=top, right=right, bottom=bottom)
