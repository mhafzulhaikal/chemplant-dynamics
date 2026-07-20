# app/hub/children/modals/sthr.py

"""STHR-specific controller modal subclasses.

Each class wires its tag's ``param_keys`` (modal key → store key) and
``param_defaults`` (initial values matching the engine's configured
initial conditions in ``cases/sthr/config.py``) into the generic
:class:`ControllerModal` / :class:`ReadOnlyControllerModal` shells
defined in :mod:`app.hub.children.modals.base` /
:mod:`app.hub.children.modals.readonly`.

Ported verbatim from the legacy ``app/pid/sthr/controller_modal.py``
during the v1 purge — same per-tag constants, same titles, same defaults
(Kc=6.10 / tauI=2.30 / tauD=0.58 for TIC-100 etc.).
"""

from __future__ import annotations

from nicegui import ui

from app.hub.children.modals.base import ControllerModal
from app.hub.children.modals.readonly import ReadOnlyControllerModal
from app.hub.local_store import LocalStore

__all__ = [
    'Tic100ControllerModal',
    'Fi100ControllerModal',
    'Fi101ControllerModal',
    'Ti100ControllerModal',
    'Li100ControllerModal',
    'Fi102ControllerModal',
    'Vp100ControllerModal',
]


class Tic100ControllerModal(ControllerModal):
    """TIC-100 — Stirred tank heater temperature controller."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        param_keys = {
            'status': 'tic_status',
            'sp': 'sp',
            'pv': 'pv',
            'op': 'op',
            'kc': 'kc',
            'tau_i': 'tau_i',
            'tau_d': 'tau_d',
        }
        # Defaults match ``cases.sthr.config.CONTROLLER_INPUT`` so
        # the modal shows the same numbers the engine was initialized
        # with (Kc=6.10, tauI=2.30, tauD=0.58).
        param_defaults = {
            'sp': 150.0,
            'pv': 150.0,
            'op': 82.3,
            'kc': 6.10,
            'tau_i': 2.30,
            'tau_d': 0.58,
        }
        try:
            from cases.sthr.config import (
                ACTUATOR_INPUT,
                CONTROLLER_INPUT,
                PLANT_OUTPUT,
                REFERENCE_INPUT,
            )

            param_defaults['sp'] = float(REFERENCE_INPUT.get('TSP-100.SP', 150.0))
            param_defaults['pv'] = float(PLANT_OUTPUT.get('STHR.T', 150.0))
            param_defaults['op'] = float(ACTUATOR_INPUT.get('TV-100.M', 82.3))
            param_defaults['kc'] = float(CONTROLLER_INPUT.get('TC-100.Kc', 6.10))
            param_defaults['tau_i'] = float(CONTROLLER_INPUT.get('TC-100.tauI', 2.30))
            param_defaults['tau_d'] = float(CONTROLLER_INPUT.get('TC-100.tauD', 0.58))
        except ImportError:
            pass
        super().__init__(
            store,
            html_element,
            'TIC-100',
            param_keys,
            param_defaults=param_defaults,
            title='TIC-100 Controller Parameters',
        )


class Fi100ControllerModal(ReadOnlyControllerModal):
    """FI-100 — Steam flow indicator (dynamic)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        self._tic_status_is_off = False
        super().__init__(
            html_element=html_element,
            controller_tag='FI-100',
            unit='lb/min',
            pv_key='fi100_pv',
            sp_key=None,  # Set dynamically in refresh_modal_values
            pv_default=42.23,
            title='FI-100 — Steam Flow',
            store=store,
            decimals=1,
        )

    @property
    def modal_type(self) -> str:
        if self.tic_status_is_off:
            return 'indicator_editable'
        return 'indicator_readonly'

    @property
    def tic_status_is_off(self) -> bool:
        return self._tic_status_is_off

    @tic_status_is_off.setter
    def tic_status_is_off(self, value: bool) -> None:
        self._tic_status_is_off = value

    def refresh_modal_values(
        self, force_op_refresh: bool = False, force_sp_refresh: bool = False
    ) -> None:
        tic_status_code = self.store.get('tic_status', 2.0)
        self.tic_status_is_off = tic_status_code == 0.0

        self.sp_key = 'steam_flow' if self.tic_status_is_off else None

        if hasattr(self, 'pv_input'):
            if self.tic_status_is_off:
                self.pv_input.props(remove='readonly')
                self.pv_input.classes(remove='ctrl-param-readonly-value-text')
            else:
                self.pv_input.props(add='readonly')
                self.pv_input.classes(add='ctrl-param-readonly-value-text')
            self.pv_input.update()

        super().refresh_modal_values(force_op_refresh, force_sp_refresh)


class Fi101ControllerModal(ReadOnlyControllerModal):
    """FI-101 — Feed flow controller / indicator."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='FI-101',
            unit='ft³/min',
            pv_key='fi101_pv',
            sp_key='feed_flow',
            pv_default=15.0,
            title='FI-101 — Feed Flow',
            store=store,
            decimals=3,
        )


class Ti100ControllerModal(ReadOnlyControllerModal):
    """TI-100 — Feed temperature controller / indicator."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element=html_element,
            controller_tag='TI-100',
            unit='°F',
            pv_key='ti100_pv',
            sp_key='feed_temp',
            pv_default=100.0,
            title='TI-100 — Feed Temp',
            store=store,
            decimals=1,
        )


class Li100ControllerModal(ReadOnlyControllerModal):
    """LI-100 — Tank level indicator (read-only)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element,
            'LI-100',
            unit='ft³',
            description='Tank level indicator on the stirred tank heater.',
            pv_key='li100_pv',
            pv_default=120.0,
            title='LI-100 — Level',
            store=store,
        )


class Fi102ControllerModal(ReadOnlyControllerModal):
    """FI-102 — Product flow indicator (read-only)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element,
            'FI-102',
            unit='ft³/min',
            description='Product flow indicator on the pump discharge line.',
            pv_key='fi102_pv',
            pv_default=15.0,
            title='FI-102 — Product Flow',
            store=store,
        )


class Vp100ControllerModal(ReadOnlyControllerModal):
    """VP-100 — Steam valve position indicator (read-only)."""

    def __init__(self, store: LocalStore, html_element: ui.element) -> None:
        super().__init__(
            html_element,
            'VP-100',
            unit='%',
            description=('Control valve position indicator on the steam feed line.'),
            pv_key='vp100_pv',
            pv_default=82.3,
            title='VP-100 — Valve Position',
            store=store,
        )
