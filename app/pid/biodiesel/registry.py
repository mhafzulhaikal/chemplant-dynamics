# app/pid/biodiesel/registry.py

"""Biodiesel :class:`ControllerRegistry`.

Biodiesel has 5 control loops: LIC-100 (level), TIC-100 (temp),
FIC-100/101/102 (oil / methanol / NaOH feed). Each contributes SP + PV +
OP + tuning + status. Plus auxiliary indicators (TI-100..104, FI-100,
FI-101, PI-100, LV-100, TV-100, FV-100..102 valve positions).

Same role as :mod:`app.pid.sthr.registry` — single source of truth for
engine_tag ↔ modal_key ↔ svg_id ↔ unit ↔ decimals.
"""

from __future__ import annotations

from app.hub.controller_registry import ControllerRegistry, ControllerSpec


def _loop_specs(
    prefix: str,  # e.g. 'lic', 'tic', 'fic100', 'fic101', 'fic102'
    pv_tag: str,  # 'biodiesel_reactor.h'
    sp_tag: str,  # 'LSP-100.SP'
    # 'LV-100.M' (actuator .M — writable for manual mode)
    op_tag: str,
    # 'LC-100.M' (controller .M — read-only, feeds readback)
    op_readback_tag: str,
    kc_tag: str,  # 'LC-100.Kc'
    taui_tag: str,  # 'LC-100.tauI'
    taud_tag: str,  # 'LC-100.tauD'
    vp_tag: str,  # 'LV-100.vp'
    svg_id: str,  # 'lic-100'
    vp_svg_id: str,  # 'lv-100'
    pv_unit: str,  # 'm', 'K', 'm³/s'
    pv_decimals: int,  # 3 / 2 / 6
    pv_range: tuple[float, float],
    title: str,
) -> list[ControllerSpec]:
    return [
        ControllerSpec(
            modal_key=f'{prefix}_pv',
            engine_tag=pv_tag,
            svg_id=svg_id,
            unit=pv_unit,
            decimals=pv_decimals,
            role='pv',
            writable=False,
            range=pv_range,
            title=title,
        ),
        ControllerSpec(
            modal_key=f'{prefix}_sp',
            engine_tag=sp_tag,
            svg_id=None,
            unit=pv_unit,
            decimals=pv_decimals,
            role='sp',
            writable=True,
            range=pv_range,
        ),
        # Read-only controller output readback. Declared BEFORE the
        # writable OP spec so the writable spec overwrites the
        # engine-tag index, and the readback populates the OP field
        # via derived_from mirroring in automatic mode.
        ControllerSpec(
            modal_key=f'{prefix}_op_readback',
            engine_tag=op_readback_tag,
            svg_id=None,
            unit='%CO',
            decimals=1,
            role='op',
            writable=False,
            range=(0.0, 100.0),
        ),
        # Writable MV target — actuator .M input (used in manual
        # mode). The derived_from link means the OP field displays
        # the controller output in automatic mode.
        ControllerSpec(
            modal_key=f'{prefix}_op',
            engine_tag=op_tag,
            svg_id=None,
            unit='%CO',
            decimals=1,
            role='op',
            writable=True,
            range=(0.0, 100.0),
            derived_from=f'{prefix}_op_readback',
        ),
        ControllerSpec(
            modal_key=f'{prefix}_kc',
            engine_tag=kc_tag,
            svg_id=None,
            unit='%CO/%TO',
            decimals=2,
            role='tuning',
            writable=True,
        ),
        ControllerSpec(
            modal_key=f'{prefix}_tau_i',
            engine_tag=taui_tag,
            svg_id=None,
            unit='min',
            decimals=2,
            role='tuning',
            writable=True,
        ),
        ControllerSpec(
            modal_key=f'{prefix}_tau_d',
            engine_tag=taud_tag,
            svg_id=None,
            unit='min',
            decimals=2,
            role='tuning',
            writable=True,
        ),
        ControllerSpec(
            modal_key=f'{prefix}_status',
            engine_tag=None,
            svg_id=None,
            unit='',
            decimals=0,
            role='status',
            writable=True,
        ),
        ControllerSpec(
            modal_key=f'{prefix}_vp',
            engine_tag=vp_tag,
            svg_id=vp_svg_id,
            unit='%',
            decimals=1,
            role='pv',
            writable=False,
            range=(0.0, 100.0),
            title=f'{title} valve',
        ),
    ]


_SPECS: list[ControllerSpec] = []

# 5 control loops
_SPECS += _loop_specs(
    'lic',
    pv_tag='biodiesel_reactor.h',
    sp_tag='LSP-100.SP',
    op_tag='LV-100.M',
    op_readback_tag='LC-100.M',
    kc_tag='LC-100.Kc',
    taui_tag='LC-100.tauI',
    taud_tag='LC-100.tauD',
    vp_tag='LV-100.vp',
    svg_id='lic-100',
    vp_svg_id='lv-100',
    pv_unit='m',
    pv_decimals=2,
    pv_range=(0.0, 3.0),
    title='Level Controller',
)
_SPECS += _loop_specs(
    'tic',
    pv_tag='biodiesel_reactor.T',
    sp_tag='TSP-100.SP',
    op_tag='TV-100.M',
    op_readback_tag='TC-100.M',
    kc_tag='TC-100.Kc',
    taui_tag='TC-100.tauI',
    taud_tag='TC-100.tauD',
    vp_tag='TV-100.vp',
    svg_id='tic-100',
    vp_svg_id='tv-100',
    pv_unit='K',
    pv_decimals=2,
    pv_range=(273.15, 368.15),
    title='Temperature Controller',
)
_SPECS += _loop_specs(
    'fic100',
    pv_tag='FV-100.F',
    sp_tag='FSP-100.SP',
    op_tag='FV-100.M',
    op_readback_tag='FC-100.M',
    kc_tag='FC-100.Kc',
    taui_tag='FC-100.tauI',
    taud_tag='FC-100.tauD',
    vp_tag='FV-100.vp',
    svg_id='fic-100',
    vp_svg_id='fv-100',
    pv_unit='m³/h',
    pv_decimals=3,
    pv_range=(0.0, 1e-3),
    title='Oil Feed Controller',
)
_SPECS += _loop_specs(
    'fic101',
    pv_tag='FV-101.F',
    sp_tag='FSP-101.SP',
    op_tag='FV-101.M',
    op_readback_tag='FC-101.M',
    kc_tag='FC-101.Kc',
    taui_tag='FC-101.tauI',
    taud_tag='FC-101.tauD',
    vp_tag='FV-101.vp',
    svg_id='fic-101',
    vp_svg_id='fv-101',
    pv_unit='m³/h',
    pv_decimals=3,
    pv_range=(0.0, 1e-3),
    title='Methanol Feed Controller',
)
_SPECS += _loop_specs(
    'fic102',
    pv_tag='FV-102.F',
    sp_tag='FSP-102.SP',
    op_tag='FV-102.M',
    op_readback_tag='FC-102.M',
    kc_tag='FC-102.Kc',
    taui_tag='FC-102.tauI',
    taud_tag='FC-102.tauD',
    vp_tag='FV-102.vp',
    svg_id='fic-102',
    vp_svg_id='fv-102',
    pv_unit='m³/h',
    pv_decimals=3,
    pv_range=(0.0, 1e-3),
    title='NaOH Feed Controller',
)

# Auxiliary indicators (with SVG controller cards).
# TI-100..104, FI-100, FI-101, PI-100 all have SVG <text>
# elements that must be seeded so the card shows the initial value
# before the first engine step arrives.
_SPECS += [
    ControllerSpec(
        modal_key='ti100_pv',
        engine_tag='biodiesel_reactor.T_oil',
        svg_id='ti-100',
        unit='K',
        decimals=2,
        role='pv',
        writable=False,
        range=(273.15, 368.15),
        title='Oil Feed Temperature',
    ),
    ControllerSpec(
        modal_key='ti101_pv',
        engine_tag='biodiesel_reactor.T_MeOH',
        svg_id='ti-101',
        unit='K',
        decimals=2,
        role='pv',
        writable=False,
        range=(273.15, 368.15),
        title='Methanol Feed Temperature',
    ),
    ControllerSpec(
        modal_key='ti102_pv',
        engine_tag='biodiesel_reactor.T_NaOH',
        svg_id='ti-102',
        unit='K',
        decimals=2,
        role='pv',
        writable=False,
        range=(273.15, 368.15),
        title='NaOH Feed Temperature',
    ),
    ControllerSpec(
        modal_key='ti103_pv',
        engine_tag='biodiesel_reactor.T_coolant_in',
        svg_id='ti-103',
        unit='K',
        decimals=2,
        role='pv',
        writable=False,
        range=(273.15, 368.15),
        title='Coolant Inlet Temperature',
    ),
    ControllerSpec(
        modal_key='ti103_sp',
        engine_tag='biodiesel_reactor.T_coolant_in',
        svg_id=None,
        unit='K',
        decimals=2,
        role='sp',
        writable=True,
        range=(273.15, 368.15),
    ),
    ControllerSpec(
        modal_key='ti104_pv',
        engine_tag='biodiesel_reactor.T_coolant',
        svg_id='ti-104',
        unit='K',
        decimals=2,
        role='pv',
        writable=False,
        range=(273.15, 368.15),
        title='Jacket Outlet Temperature',
    ),
    # ── Editable input setpoints (so the modal SP slots have
    #    a writable target for TI-100/TI-101/TI-102/TI-103) ──────
    ControllerSpec(
        modal_key='ti100_sp',
        engine_tag='biodiesel_reactor.T_oil',
        svg_id=None,
        unit='K',
        decimals=2,
        role='sp',
        writable=True,
        range=(273.15, 368.15),
    ),
    ControllerSpec(
        modal_key='ti101_sp',
        engine_tag='biodiesel_reactor.T_MeOH',
        svg_id=None,
        unit='K',
        decimals=2,
        role='sp',
        writable=True,
        range=(273.15, 368.15),
    ),
    ControllerSpec(
        modal_key='ti102_sp',
        engine_tag='biodiesel_reactor.T_NaOH',
        svg_id=None,
        unit='K',
        decimals=2,
        role='sp',
        writable=True,
        range=(273.15, 368.15),
    ),
    ControllerSpec(
        modal_key='fi100_pv',
        engine_tag='TV-100.F',
        svg_id='fi-100',
        unit='m³/h',
        decimals=3,
        role='pv',
        writable=False,
        range=(0.0, 1e-3),
        title='Coolant Flow',
    ),
    ControllerSpec(
        modal_key='fi101_pv',
        engine_tag='LV-100.F',
        svg_id='fi-101',
        unit='m³/h',
        decimals=3,
        role='pv',
        writable=False,
        range=(0.0, 1e-3),
        title='Product Flow',
    ),
    ControllerSpec(
        modal_key='pi100_pv',
        engine_tag=None,
        svg_id='pi-100',
        unit='bar',
        decimals=2,
        role='pv',
        writable=False,
        range=(0.0, 10.0),
        title='Reactor Pressure',
    ),
]

# Engine-derived auxiliary indicators (no SVG cards).
_SPECS += [
    ControllerSpec(
        modal_key='tic_mv_flow',
        engine_tag='TV-100.F',
        svg_id=None,
        unit='m³/h',
        decimals=3,
        role='pv',
        writable=False,
    ),
    ControllerSpec(
        modal_key='tic_coolant_temp',
        engine_tag='biodiesel_reactor.T_coolant',
        svg_id=None,
        unit='K',
        decimals=2,
        role='pv',
        writable=False,
    ),
    ControllerSpec(
        modal_key='lic_mv_flow',
        engine_tag='LV-100.F',
        svg_id=None,
        unit='m³/h',
        decimals=3,
        role='pv',
        writable=False,
    ),
]


BIODIESEL_REGISTRY: ControllerRegistry = ControllerRegistry(_SPECS)


__all__ = ['BIODIESEL_REGISTRY']
