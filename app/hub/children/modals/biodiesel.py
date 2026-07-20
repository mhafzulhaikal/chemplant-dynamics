# app/hub/children/modals/biodiesel.py

"""Biodiesel-specific controller modal subclasses.

Each class wires its tag's ``param_keys`` and ``param_defaults``
into the generic :class:`ControllerModal` / :class:`ReadOnlyControllerModal`
shells. Ported verbatim from the legacy
``app/pid/biodiesel/controller_modal.py`` during the v1 purge —
same per-tag constants, same titles, same defaults (matching
``cases/biodiesel/config.py`` initial conditions).

The biodiesel case has:

- 5 tunable control loops: LIC-100 (level), TIC-100 (temperature),
  FIC-100 (oil feed), FIC-101 (methanol feed), FIC-102 (NaOH feed).
- 4 editable boundary-condition inputs: TI-100 (oil temp),
  TI-101 (methanol temp), TI-102 (NaOH temp), TI-103 (coolant inlet temp).
- 1 read-only temperature indicator: TI-104.
- 3 read-only flow / pressure indicators: FI-100, FI-101, PI-100.
- 5 read-only valve-position indicators: LV-100, TV-100,
  FV-100, FV-101, FV-102.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from app.hub.children.modals.base import ControllerModal
from app.hub.children.modals.readonly import ReadOnlyControllerModal
from app.hub.local_store import LocalStore

__all__ = [
    'ValvePositionModal',
    # Tunable control loops
    'Lic100ControllerModal',
    'Tic100ControllerModal',
    'Fic100ControllerModal',
    'Fic101ControllerModal',
    'Fic102ControllerModal',
    # Editable input indicators (boundary conditions)
    'Ti100ControllerModal',
    'Ti101ControllerModal',
    'Ti102ControllerModal',
    # Read-only indicators
    'Ti103ControllerModal',
    'Ti104ControllerModal',
    'Fi100ControllerModal',
    'Fi101ControllerModal',
    'Pi100ControllerModal',
    # Read-only valve positions
    'Lv100ValvePositionModal',
    'Tv100ValvePositionModal',
    'Fv100ValvePositionModal',
    'Fv101ValvePositionModal',
    'Fv102ValvePositionModal',
]


# ── Valve position modal ──
# Valve-position cards (LV-100, TV-100, FV-100..102) display a
# percentage (0–100 %vp) that the control loop writes into the
# actuator. The shape is the same as a read-only controller modal
# but with a 0..100 % unit range.


class ValvePositionModal(ReadOnlyControllerModal):
    """Read-only valve-position indicator.

    Mirrors :class:`ReadOnlyControllerModal` but formats the live value
    as a percentage (0–100 %vp) — the same scale the rest of the
    biodiesel case uses for valve-position outputs.
    """

    def __init__(
        self,
        store: Any,
        html_element: ui.element,
        controller_tag: str,
        pv_key: str,
        pv_default: float = 50.0,
        description: str = '',
        title: str | None = None,
    ) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag=controller_tag,
            unit='%',
            description=description or 'Valve position indicator.',
            pv_key=pv_key,
            pv_default=pv_default,
            title=title or f'{controller_tag} — Valve Position',
            store=store,
        )


# ── Tunable controllers (5 control loops) ──


class Lic100ControllerModal(ControllerModal):
    """LIC-100 — Reactor level controller (LC-100 → LV-100)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        param_keys: dict[str, str] = {
            'status': 'lic_status',
            'sp': 'lic_sp',
            'pv': 'lic_pv',
            'op': 'lic_op',
            'kc': 'lic_kc',
            'tau_i': 'lic_tau_i',
            'tau_d': 'lic_tau_d',
        }
        # Defaults match ``cases.biodiesel.config.CONTROLLER_INPUT``
        # and ``REFERENCE_INPUT`` (LC-100 SP, Kc, tauI, tauD) so the
        # modal shows the same numbers the engine was initialized
        # with.
        param_defaults: dict[str, float] = {
            'sp': 1.50,
            'pv': 1.50,
            'op': 50.0,
            'kc': 77.80,
            'tau_i': 0.0,
            'tau_d': 0.0,
        }
        try:
            from cases.biodiesel.config import (
                ACTUATOR_INPUT,
                CONTROLLER_INPUT,
                PLANT_STATE,
                REFERENCE_INPUT,
            )

            param_defaults['sp'] = float(REFERENCE_INPUT.get('LSP-100.SP', 1.50))
            param_defaults['pv'] = float(PLANT_STATE.get('h', 1.50))
            param_defaults['op'] = float(ACTUATOR_INPUT.get('LV-100.M', 50.0))
            param_defaults['kc'] = float(CONTROLLER_INPUT.get('LC-100.Kc', 77.80))
            param_defaults['tau_i'] = float(CONTROLLER_INPUT.get('LC-100.tauI', 0.0))
            param_defaults['tau_d'] = float(CONTROLLER_INPUT.get('LC-100.tauD', 0.0))
        except ImportError:
            pass
        super().__init__(
            store,
            html_element,
            'LIC-100',
            param_keys,
            param_defaults=param_defaults,
            title='LIC-100 — Level Controller',
        )


class Tic100ControllerModal(ControllerModal):
    """TIC-100 — Reactor temperature controller (TC-100 → TV-100)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        param_keys: dict[str, str] = {
            'status': 'tic_status',
            'sp': 'tic_sp',
            'pv': 'tic_pv',
            'op': 'tic_op',
            'kc': 'tic_kc',
            'tau_i': 'tic_tau_i',
            'tau_d': 'tic_tau_d',
        }
        param_defaults: dict[str, float] = {
            'sp': 333.15,
            'pv': 333.15,
            'op': 80.0,
            'kc': 10.34,
            'tau_i': 1070.07,
            'tau_d': 267.52,
        }
        try:
            from cases.biodiesel.config import (
                ACTUATOR_INPUT,
                CONTROLLER_INPUT,
                PLANT_STATE,
                REFERENCE_INPUT,
            )

            param_defaults['sp'] = float(REFERENCE_INPUT.get('TSP-100.SP', 333.15))
            param_defaults['pv'] = float(PLANT_STATE.get('T', 333.15))
            param_defaults['op'] = float(ACTUATOR_INPUT.get('TV-100.M', 80.0))
            param_defaults['kc'] = float(CONTROLLER_INPUT.get('TC-100.Kc', 10.34))
            param_defaults['tau_i'] = float(CONTROLLER_INPUT.get('TC-100.tauI', 1070.07))
            param_defaults['tau_d'] = float(CONTROLLER_INPUT.get('TC-100.tauD', 267.52))
        except ImportError:
            pass
        super().__init__(
            store,
            html_element,
            'TIC-100',
            param_keys,
            param_defaults=param_defaults,
            title='TIC-100 — Temperature Controller',
        )


class Fic100ControllerModal(ControllerModal):
    """FIC-100 — Oil feed flow controller (FC-100 → FV-100)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        param_keys: dict[str, str] = {
            'status': 'fic100_status',
            'sp': 'fic100_sp',
            'pv': 'fic100_pv',
            'op': 'fic100_op',
            'kc': 'fic100_kc',
            'tau_i': 'fic100_tau_i',
            'tau_d': 'fic100_tau_d',
        }
        param_defaults: dict[str, float] = {
            'sp': 3.29675e-04,
            'pv': 3.29675e-04,
            'op': 50.0,
            'kc': 0.33,
            'tau_i': 12.0,
            'tau_d': 0.0,
        }
        try:
            from cases.biodiesel.config import (
                ACTUATOR_INPUT,
                CONTROLLER_INPUT,
                REFERENCE_INPUT,
                SENSOR_TRANSMITTER_INPUT,
            )

            param_defaults['sp'] = float(REFERENCE_INPUT.get('FSP-100.SP', 3.29675e-04))
            param_defaults['pv'] = float(SENSOR_TRANSMITTER_INPUT.get('FT-100.PV', 3.29675e-04))
            param_defaults['op'] = float(ACTUATOR_INPUT.get('FV-100.M', 50.0))
            param_defaults['kc'] = float(CONTROLLER_INPUT.get('FC-100.Kc', 0.33))
            param_defaults['tau_i'] = float(CONTROLLER_INPUT.get('FC-100.tauI', 12.0))
            param_defaults['tau_d'] = float(CONTROLLER_INPUT.get('FC-100.tauD', 0.0))
        except ImportError:
            pass
        super().__init__(
            store,
            html_element,
            'FIC-100',
            param_keys,
            param_defaults=param_defaults,
            title='FIC-100 — Oil Feed Flow',
        )


class Fic101ControllerModal(ControllerModal):
    """FIC-101 — Methanol feed flow controller (FC-101 → FV-101)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        param_keys: dict[str, str] = {
            'status': 'fic101_status',
            'sp': 'fic101_sp',
            'pv': 'fic101_pv',
            'op': 'fic101_op',
            'kc': 'fic101_kc',
            'tau_i': 'fic101_tau_i',
            'tau_d': 'fic101_tau_d',
        }
        param_defaults: dict[str, float] = {
            'sp': 8.33750e-05,
            'pv': 8.33750e-05,
            'op': 50.0,
            'kc': 0.33,
            'tau_i': 12.0,
            'tau_d': 0.0,
        }
        try:
            from cases.biodiesel.config import (
                ACTUATOR_INPUT,
                CONTROLLER_INPUT,
                REFERENCE_INPUT,
                SENSOR_TRANSMITTER_INPUT,
            )

            param_defaults['sp'] = float(REFERENCE_INPUT.get('FSP-101.SP', 8.33750e-05))
            param_defaults['pv'] = float(SENSOR_TRANSMITTER_INPUT.get('FT-101.PV', 8.33750e-05))
            param_defaults['op'] = float(ACTUATOR_INPUT.get('FV-101.M', 50.0))
            param_defaults['kc'] = float(CONTROLLER_INPUT.get('FC-101.Kc', 0.33))
            param_defaults['tau_i'] = float(CONTROLLER_INPUT.get('FC-101.tauI', 12.0))
            param_defaults['tau_d'] = float(CONTROLLER_INPUT.get('FC-101.tauD', 0.0))
        except ImportError:
            pass
        super().__init__(
            store,
            html_element,
            'FIC-101',
            param_keys,
            param_defaults=param_defaults,
            title='FIC-101 — Methanol Feed Flow',
        )


class Fic102ControllerModal(ControllerModal):
    """FIC-102 — NaOH catalyst feed flow controller (FC-102 → FV-102)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        param_keys: dict[str, str] = {
            'status': 'fic102_status',
            'sp': 'fic102_sp',
            'pv': 'fic102_pv',
            'op': 'fic102_op',
            'kc': 'fic102_kc',
            'tau_i': 'fic102_tau_i',
            'tau_d': 'fic102_tau_d',
        }
        param_defaults: dict[str, float] = {
            'sp': 1.33405e-05,
            'pv': 1.33405e-05,
            'op': 50.0,
            'kc': 0.33,
            'tau_i': 12.0,
            'tau_d': 0.0,
        }
        try:
            from cases.biodiesel.config import (
                ACTUATOR_INPUT,
                CONTROLLER_INPUT,
                REFERENCE_INPUT,
                SENSOR_TRANSMITTER_INPUT,
            )

            param_defaults['sp'] = float(REFERENCE_INPUT.get('FSP-102.SP', 1.33405e-05))
            param_defaults['pv'] = float(SENSOR_TRANSMITTER_INPUT.get('FT-102.PV', 1.33405e-05))
            param_defaults['op'] = float(ACTUATOR_INPUT.get('FV-102.M', 50.0))
            param_defaults['kc'] = float(CONTROLLER_INPUT.get('FC-102.Kc', 0.33))
            param_defaults['tau_i'] = float(CONTROLLER_INPUT.get('FC-102.tauI', 12.0))
            param_defaults['tau_d'] = float(CONTROLLER_INPUT.get('FC-102.tauD', 0.0))
        except ImportError:
            pass
        super().__init__(
            store,
            html_element,
            'FIC-102',
            param_keys,
            param_defaults=param_defaults,
            title='FIC-102 — NaOH Catalyst Feed',
        )


# ── Read-only temperature indicators (5 sensors) ──


class Ti100ControllerModal(ReadOnlyControllerModal):
    """TI-100 — Oil feed temperature (editable boundary condition)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='TI-100',
            unit='K',
            pv_key='ti100_pv',
            sp_key='ti100_sp',
            pv_default=333.15,
            title='TI-100 — Oil Feed Temperature',
            store=store,
            decimals=2,
        )


class Ti101ControllerModal(ReadOnlyControllerModal):
    """TI-101 — Methanol feed temperature (editable boundary condition)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='TI-101',
            unit='K',
            pv_key='ti101_pv',
            sp_key='ti101_sp',
            pv_default=298.15,
            title='TI-101 — Methanol Feed Temperature',
            store=store,
            decimals=2,
        )


class Ti102ControllerModal(ReadOnlyControllerModal):
    """TI-102 — NaOH feed temperature (editable boundary condition)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='TI-102',
            unit='K',
            pv_key='ti102_pv',
            sp_key='ti102_sp',
            pv_default=298.15,
            title='TI-102 — NaOH Feed Temperature',
            store=store,
            decimals=2,
        )


class Ti103ControllerModal(ReadOnlyControllerModal):
    """TI-103 — Coolant pump discharge temperature (editable boundary
    condition)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='TI-103',
            unit='K',
            pv_key='ti103_pv',
            sp_key='ti103_sp',
            pv_default=298.15,
            title='TI-103 — Coolant Pump Discharge',
            store=store,
            decimals=2,
        )


class Ti104ControllerModal(ReadOnlyControllerModal):
    """TI-104 — Jacket outlet temperature indicator."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='TI-104',
            unit='K',
            pv_key='ti104_pv',
            pv_default=323.15,
            title='TI-104 — Jacket Outlet Temperature',
            store=store,
            decimals=2,
        )


# ── Read-only flow & pressure indicators (3 sensors) ──


class Fi100ControllerModal(ReadOnlyControllerModal):
    """FI-100 — Coolant flow indicator at the pump suction."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='FI-100',
            unit='m³/hr',
            description='Coolant flow indicator at the pump suction.',
            pv_key='fi100_pv',
            pv_default=1.5114e-04,
            title='FI-100 — Coolant Flow',
            store=store,
            decimals=6,
        )


class Fi101ControllerModal(ReadOnlyControllerModal):
    """FI-101 — Product flow indicator at the pump discharge."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='FI-101',
            unit='m³/hr',
            description='Product (FAME) flow indicator at the pump discharge.',
            pv_key='fi101_pv',
            pv_default=4.6882e-04,
            title='FI-101 — Product Flow',
            store=store,
            decimals=6,
        )


class Pi100ControllerModal(ReadOnlyControllerModal):
    """PI-100 — Reactor pressure indicator."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='PI-100',
            unit='bar',
            description='Reactor pressure indicator.',
            pv_key='pi100_pv',
            pv_default=4.0,
            title='PI-100 — Reactor Pressure',
            store=store,
            decimals=2,
        )


# ── Read-only valve positions (5 valves) ──


class Lv100ValvePositionModal(ValvePositionModal):
    """LV-100 — Level-control valve (LC-100 actuator)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            store=store,
            html_element=html_element,
            controller_tag='LV-100',
            pv_key='lic_vp',
            pv_default=50.0,
            description='Level-control valve on the FAME product line.',
            title='LV-100 — Level Valve Position',
        )


class Tv100ValvePositionModal(ValvePositionModal):
    """TV-100 — Temperature-control valve (TC-100 actuator)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            store=store,
            html_element=html_element,
            controller_tag='TV-100',
            pv_key='tic_vp',
            pv_default=50.0,
            description=('Temperature-control valve on the coolant jacket inlet.'),
            title='TV-100 — Coolant Valve Position',
        )


class Fv100ValvePositionModal(ValvePositionModal):
    """FV-100 — Oil feed valve (FC-100 actuator)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            store=store,
            html_element=html_element,
            controller_tag='FV-100',
            pv_key='fic100_vp',
            pv_default=50.0,
            description='Oil feed valve on the FC-100 feed line.',
            title='FV-100 — Oil Feed Valve Position',
        )


class Fv101ValvePositionModal(ValvePositionModal):
    """FV-101 — Methanol feed valve (FC-101 actuator)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            store=store,
            html_element=html_element,
            controller_tag='FV-101',
            pv_key='fic101_vp',
            pv_default=50.0,
            description='Methanol feed valve on the FC-101 feed line.',
            title='FV-101 — Methanol Feed Valve Position',
        )


class Fv102ValvePositionModal(ValvePositionModal):
    """FV-102 — NaOH feed valve (FC-102 actuator)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            store=store,
            html_element=html_element,
            controller_tag='FV-102',
            pv_key='fic102_vp',
            pv_default=50.0,
            description='NaOH catalyst feed valve on the FC-102 feed line.',
            title='FV-102 — NaOH Feed Valve Position',
        )
