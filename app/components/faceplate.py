# app/components/faceplate.py

"""Faceplate spec + modal inference helpers (legacy right-drawer
entry point retained for backward compatibility).

The right-drawer faceplate was replaced by a floating
:class:`ui.dialog` (see :mod:`app.components.faceplate_dialog`).
This module now hosts the shared :class:`FaceplateSpec` dataclass
and the :func:`infer_faceplate_spec` helper that the new dialog
uses to derive per-tag display metadata from a controller
modal's public API. Legacy code that imported
``FaceplatePanel`` from this module is updated at the call sites
to use :class:`FaceplateDialog`; the name is intentionally not
re-exported so an accidental import fails loudly instead of
silently instantiating the wrong class.

Background
----------

The faceplate is a per-controller extension of the modal that
mirrors the look-and-feel of a DCS HMI:

    ┌──────────────────────────────┐
    │ TAG    Description     [×]   │
    │ mode badge / status          │
    │                              │
    │   PV          SP          OP │
    │  ▓▓▓▓▓▓      ▓▓▓▓▓▓     ▓▓▓▓ │
    │  150.0       150.0      82.3 │
    │   °F          °F          %  │
    │                              │
    │ ── Operational Parameters ── │
    │ Mode [Auto ▾]                 │
    │ SP   [ 150.0 ]   °F           │
    │ PV   [ 150.0 ]   °F           │
    │ OP   [  82.3 ]   %            │
    │                              │
    │ ── Controller Parameters ──  │
    │ Kc   [  6.10 ]  %CO/%TO       │
    │ τI   [  2.30 ]  min           │
    │ τD   [  0.58 ]  min           │
    │                              │
    │ [ Apply ]                     │
    └──────────────────────────────┘

The vertical bargraphs are pure CSS. A ``.faceplate-bar-fill``
element is positioned at the bottom of its track and its
``height`` is updated in % by the live flusher. The fill colours
are DCS standard: PV = process yellow, SP = setpoint cyan, OP =
output magenta/green. The bargraph also draws a horizontal SP
marker so the operator can see at a glance how far PV is from
SP.

The body content (header, bargraphs, operational + tuning
inputs, Apply button) now lives inside a ``ui.dialog`` (see
:mod:`app.components.faceplate_dialog`); only the per-tag
display metadata and the modal-inference helper remain here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.pid.biodiesel.ui_config import (
    CONTROLLER_DRAWER_CONFIG as BIODIESEL_CONTROLLER_DRAWER_CONFIG,
)
from app.pid.sthr.ui_config import CONTROLLER_DRAWER_CONFIG as STHR_CONTROLLER_DRAWER_CONFIG

# ============================================================
# CONTROLLER METADATA
# ============================================================
#
# Per-tag display metadata used by the faceplate. Mirrors
# ``app.config.DISPLAY_MAP`` for units and ``DISPLAY_MAP`` ranges
# / defaults from the modal classes for SP/PV/OP keys.
#
# Adding a new controller means adding a row here AND registering
# the modal in the page's ``render_*_pid_svg`` builder — the
# faceplate discovers which tags to show from the registered
# controller_modals dict on the html element.


class ModalType(Enum):
    CONTROLLER = 'controller'
    INDICATOR_EDITABLE = 'indicator_editable'
    INDICATOR_READONLY = 'indicator_readonly'
    VALVE_POSITION = 'valve_position'


@dataclass(frozen=True)
class FaceplateSpec:
    """Static display metadata for a single controller tag."""

    tag: str  # 'TIC-100'
    svg_id: str  # 'tic-100'
    title: str  # 'Temperature Controller'
    pv_unit: str  # '°F'
    sp_unit: str  # '°F' (may differ from pv_unit for FI-101)
    op_unit: str  # '%' / '%CO'
    pv_min: float
    pv_max: float
    sp_min: float
    sp_max: float
    op_min: float  # typically 0
    op_max: float  # typically 100
    sp_step: float
    pv_step: float
    op_step: float
    kc_min: float
    kc_max: float
    kc_step: float
    taui_min: float
    taui_max: float
    taui_step: float
    taud_min: float
    taud_max: float
    taud_step: float
    pv_decimals: int
    sp_decimals: int
    op_decimals: int
    modal_type: ModalType
    has_mode: bool
    has_op: bool
    has_tuning: bool
    # Optional bargraph overrides (e.g. SP bargraph is shown
    # only when the controller has a writable setpoint).
    show_sp_bar: bool = True
    show_op_bar: bool = True


# ============================================================
# SPEC INFERENCE
# ============================================================
#
# Shared by :mod:`app.components.faceplate_dialog` so the new
# dialog and any future host (a non-floating right pane, an
# embedded mini-faceplate, etc.) can derive per-tag metadata
# from a controller modal's public API without duplicating the
# unit / range / decimal-place logic.

# Per-svg-id decimal place map. Mirrors the legacy flusher's
# per-tag map; kept here as a module-level constant so a future
# host can reuse it without re-importing the dialog.
_DECIMALS_MAP = {
    # STHR
    'tic-100': (1, 1, 1),
    'fi-100': (2, 1, 1),
    'fi-101': (1, 1, 1),
    'ti-100': (1, 1, 1),
    'li-100': (1, 1, 1),
    'fi-102': (1, 1, 1),
    'vp-100': (1, 1, 1),
    # Biodiesel — tunable controllers (unique tags)
    'lic-100': (2, 2, 1),
    'fic-100': (6, 6, 1),
    'fic-101': (6, 6, 1),
    'fic-102': (6, 6, 1),
    # Biodiesel — indicators (unique tags)
    'ti-101': (2, 2, 1),
    'ti-102': (2, 2, 1),
    'ti-103': (2, 2, 1),
    'ti-104': (2, 2, 1),
    'pi-100': (2, 2, 1),
    # Biodiesel — valve positions (unique tags)
    'lv-100': (1, 1, 1),
    'tv-100': (1, 1, 1),
    'fv-100': (1, 1, 1),
    'fv-101': (1, 1, 1),
    'fv-102': (1, 1, 1),
}

# Biodiesel-specific decimal overrides for tags shared with STHR.
# Used only when the modal originates from the biodiesel module.
_BIODIESEL_DECIMALS_MAP: dict[str, tuple[int, int, int]] = {
    'tic-100': (2, 2, 1),
    'ti-100': (2, 2, 1),
    'fi-100': (6, 6, 1),
    'fi-101': (6, 6, 1),
}


def infer_faceplate_spec(modal: Any, registry: Any | None = None) -> FaceplateSpec:
    """Build a :class:`FaceplateSpec` from a modal's public API.

    Read-only modals (no SP, no OP) collapse to a single PV bargraph.
    Tunable modals keep all three bargraphs.

    The function is intentionally pure (no I/O, no logging, no fallbacks
    that swallow exceptions silently) so the caller gets a consistent
    spec for a given modal.
    """
    tag = str(getattr(modal, 'controller_tag', '')).strip().upper()
    svg_id = tag.lower()

    # Unit / range resolution
    pv_unit = str(getattr(modal, 'pv_unit', '') or '') or str(getattr(modal, 'unit', '') or '')
    sp_unit = pv_unit
    op_unit = str(getattr(modal, 'mv_unit', '') or '%CO')

    # Range lookups — use biodiesel config when modal comes from
    # the biodiesel process; otherwise fall back to STHR config.
    _is_biodiesel_mod = 'biodiesel' in type(modal).__module__
    _cfg_src = (
        BIODIESEL_CONTROLLER_DRAWER_CONFIG if _is_biodiesel_mod else STHR_CONTROLLER_DRAWER_CONFIG
    )
    cfg = _cfg_src.get(svg_id, {}) if isinstance(_cfg_src, dict) else {}
    params = cfg.get('params', []) if isinstance(cfg, dict) else []

    has_mode = not isinstance(modal, type(None)) and hasattr(modal, 'mode_options')
    has_op = bool(getattr(modal, 'supports_operator_output', False))

    def _param_meta(ui_key: str) -> dict:
        for item in params:
            if not isinstance(item, dict):
                continue
            if item.get('key') == ui_key or item.get('field') == ui_key:
                return item
        return {}

    sp_meta = _param_meta('sp')
    sp_min = float(sp_meta.get('min', 0.0) if sp_meta.get('min') is not None else 0.0)
    sp_max = float(sp_meta.get('max', 1000.0) if sp_meta.get('max') is not None else 1000.0)
    sp_step = float(sp_meta.get('step', 0.01) or 0.01)

    if svg_id == 'fi-101':
        ff_meta = _param_meta('feed_flow')
        sp_min = float(ff_meta.get('min', 0.0) if ff_meta.get('min') is not None else 0.0)
        sp_max = float(ff_meta.get('max', 200.0) if ff_meta.get('max') is not None else 200.0)
        sp_step = float(ff_meta.get('step', 0.01) or 0.01)
    if svg_id == 'ti-100':
        ft_meta = _param_meta('feed_temp')
        sp_min = float(ft_meta.get('min', 50.0) if ft_meta.get('min') is not None else 50.0)
        sp_max = float(ft_meta.get('max', 250.0) if ft_meta.get('max') is not None else 250.0)
        sp_step = float(ft_meta.get('step', 0.01) or 0.01)

    pv_meta = _param_meta('pv')
    pv_min = float(pv_meta.get('min', sp_min) if pv_meta.get('min') is not None else sp_min)
    pv_max = float(pv_meta.get('max', sp_max) if pv_meta.get('max') is not None else sp_max)
    pv_step = float(pv_meta.get('step', sp_step) or sp_step)

    if pv_meta.get('min') is None and not params:
        if 'lb/min' in pv_unit:
            pv_min, pv_max = 0.0, 100.0
        elif '%' in pv_unit and ('vp' in svg_id or 'valve' in svg_id.lower()):
            pv_min, pv_max = 0.0, 100.0
        elif 'ft³' in pv_unit:
            pv_min, pv_max = 0.0, 200.0
        else:
            pv_min, pv_max = 0.0, 100.0

    has_tuning = bool(getattr(modal, 'has_tuning', False))
    has_mode = not isinstance(modal, type(None)) and hasattr(modal, 'mode_options')
    has_op = bool(getattr(modal, 'supports_operator_output', False))

    # Infer ModalType
    if modal is not None and hasattr(modal, 'modal_type') and modal.modal_type is not None:
        try:
            modal_type = ModalType(modal.modal_type)
        except ValueError:
            modal_type = ModalType.CONTROLLER
    else:
        if has_tuning or has_mode:
            modal_type = ModalType.CONTROLLER
        elif modal is not None and hasattr(modal, 'sp_key') and modal.sp_key:
            modal_type = ModalType.INDICATOR_EDITABLE
        elif '%' in pv_unit and (
            'vp' in svg_id
            or 'valve' in svg_id.lower()
            or 'fv-' in svg_id
            or 'tv-' in svg_id
            or 'lv-' in svg_id
        ):
            modal_type = ModalType.VALVE_POSITION
        else:
            modal_type = ModalType.INDICATOR_READONLY

    # Bargraph layout — tunable controllers keep the full
    # three-bar layout (PV, SP, OP). Controllers with OP
    # but no tuning show PV + OP. Read-only indicators
    # collapse to a single PV bar.
    show_sp_bar = bool(has_tuning) or modal_type == ModalType.CONTROLLER
    show_op_bar = bool(has_tuning or has_op)

    op_meta = _param_meta('op')
    op_min = float(op_meta.get('min', 0.0) if op_meta.get('min') is not None else 0.0)
    op_max = float(op_meta.get('max', 100.0) if op_meta.get('max') is not None else 100.0)
    op_step = float(op_meta.get('step', 0.01) or 0.01)

    kc_meta = _param_meta('kc')
    kc_min = float(kc_meta.get('min', 0.0) if kc_meta.get('min') is not None else 0.0)
    kc_max = float(kc_meta.get('max', 1000.0) if kc_meta.get('max') is not None else 1000.0)
    kc_step = float(kc_meta.get('step', 0.01) or 0.01)

    taui_meta = _param_meta('tau_i')
    taui_min = float(taui_meta.get('min', 0.0) if taui_meta.get('min') is not None else 0.0)
    taui_max = float(taui_meta.get('max', 1000.0) if taui_meta.get('max') is not None else 1000.0)
    taui_step = float(taui_meta.get('step', 0.01) or 0.01)

    taud_meta = _param_meta('tau_d')
    taud_min = float(taud_meta.get('min', 0.0) if taud_meta.get('min') is not None else 0.0)
    taud_max = float(taud_meta.get('max', 1000.0) if taud_meta.get('max') is not None else 1000.0)
    taud_step = float(taud_meta.get('step', 0.01) or 0.01)

    pv_d, sp_d, op_d = None, None, None
    if registry is not None:
        try:
            value_keys = getattr(modal, 'value_keys', {})
            pv_key = value_keys.get('pv')
            sp_key = value_keys.get('sp')
            op_key = value_keys.get('op')
            if pv_key:
                spec = registry.get_by_modal_key(pv_key)
                if spec:
                    pv_d = spec.decimals
            if sp_key:
                spec = registry.get_by_modal_key(sp_key)
                if spec:
                    sp_d = spec.decimals
            if op_key:
                spec = registry.get_by_modal_key(op_key)
                if spec:
                    op_d = spec.decimals
        except Exception:
            pass

    if pv_d is None or sp_d is None or op_d is None:
        if _is_biodiesel_mod:
            def_pv_d, def_sp_d, def_op_d = _BIODIESEL_DECIMALS_MAP.get(
                svg_id, _DECIMALS_MAP.get(svg_id, (1, 1, 1))
            )
        else:
            def_pv_d, def_sp_d, def_op_d = _DECIMALS_MAP.get(svg_id, (1, 1, 1))
        pv_d = pv_d if pv_d is not None else def_pv_d
        sp_d = sp_d if sp_d is not None else def_sp_d
        op_d = op_d if op_d is not None else def_op_d

    return FaceplateSpec(
        tag=tag,
        svg_id=svg_id,
        title=str(getattr(modal, 'title', tag) or tag),
        pv_unit=pv_unit,
        sp_unit=sp_unit,
        op_unit=op_unit,
        pv_min=pv_min,
        pv_max=pv_max,
        sp_min=sp_min,
        sp_max=sp_max,
        op_min=op_min,
        op_max=op_max,
        sp_step=sp_step,
        pv_step=pv_step,
        op_step=op_step,
        kc_min=kc_min,
        kc_max=kc_max,
        kc_step=kc_step,
        taui_min=taui_min,
        taui_max=taui_max,
        taui_step=taui_step,
        taud_min=taud_min,
        taud_max=taud_max,
        taud_step=taud_step,
        pv_decimals=pv_d,
        sp_decimals=sp_d,
        op_decimals=op_d,
        modal_type=modal_type,
        has_mode=has_mode,
        has_op=has_op,
        has_tuning=has_tuning,
        show_sp_bar=show_sp_bar,
        show_op_bar=show_op_bar,
    )


# ============================================================
# LEGACY COMPATIBILITY
# ============================================================
#
# The legacy ``FaceplatePanel`` was a right-drawer faceplate.
# It has been replaced by
# :class:`app.components.faceplate_dialog.FaceplateDialog`
# (a ``ui.dialog`` with drag / resize / minimize). Importing the
# old name raises a clear error so callers that haven't been
# updated get a fast, loud failure with a migration hint
# instead of silently instantiating the wrong class.
#
# If you reach this error, replace::
#
#     from app.components.faceplate import FaceplatePanel
#     panel = FaceplatePanel()
#
# with::
#
#     from app.components.faceplate_dialog import (
#         FaceplateDialog,
#         FaceplateDialogConfig,
#     )
#     dialog = FaceplateDialog(FaceplateDialogConfig(case_slug='sthr'))
#     dialog.build()
#     for tag, modal in modals.items():
#         modal.set_faceplate(dialog)
#         dialog.register_modal(modal)
#
# Public methods on the new dialog match the legacy panel
# (``register_modal``, ``open_for``, ``close``, ``refresh``,
# ``set_drawer`` (no-op)) so the call sites only need to swap
# the class and constructor.


class FaceplatePanel:
    """Removed in favor of
    :class:`app.components.faceplate_dialog.FaceplateDialog`.

    Kept as a class so the existing ``from app.components.faceplate
    import FaceplatePanel`` import path resolves. Attempting to
    *instantiate* the class raises a clear error with the
    migration hint so call sites that haven't been updated get a
    fast, loud failure instead of silently instantiating the
    wrong class.

    Migration::

        # before
        from app.components.faceplate import FaceplatePanel
        panel = FaceplatePanel()
        panel.set_drawer(drawer_aside)

        # after
        from app.components.faceplate_dialog import (
            FaceplateDialog,
            FaceplateDialogConfig,
        )
        dialog = FaceplateDialog(
            FaceplateDialogConfig(case_slug='sthr'),
        )
        dialog.build()  # construct the dialog DOM once
        for tag, modal in modals.items():
            modal.set_faceplate(dialog)
            dialog.register_modal(modal)

    Public methods on the new dialog (``register_modal``,
    ``open_for``, ``close``, ``refresh``, ``set_drawer`` as a
    no-op) match the legacy panel exactly.
    """

    def __init__(self, *_args, **_kwargs) -> None:
        raise RuntimeError(
            'FaceplatePanel has been removed. The faceplate is '
            'now a ui.dialog — import FaceplateDialog from '
            'app.components.faceplate_dialog instead.\n\n'
            'Migration:\n'
            '    from app.components.faceplate_dialog import (\n'
            '        FaceplateDialog, FaceplateDialogConfig,\n'
            '    )\n'
            '    dialog = FaceplateDialog(\n'
            "        FaceplateDialogConfig(case_slug='sthr'),\n"
            '    )\n'
            '    dialog.build()\n'
            "    # The dialog's register_modal / open_for / close /\n"
            '    # refresh / set_drawer (no-op) API matches the\n'
            '    # legacy FaceplatePanel exactly.\n'
        )


__all__ = [
    'FaceplateSpec',
    'FaceplatePanel',  # legacy shim — raises on instantiation
    'infer_faceplate_spec',
    'ModalType',
]
