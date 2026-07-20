from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from models import (
    ActuatorSystem,
    BiodieselReactorSystem,
    ControllerSystem,
    SensorTransmitterSystem,
    SetPointSystem,
)
from systems.builders.common import build_interconnected_system
from systems.configs.biodiesel_config import (
    ACTUATOR_PARAMS,
    CONTROLLER_PARAMS,
    PROCESS_PARAMS,
    SENSOR_TRANSMITTER_PARAMS,
    SETPOINT_PARAMS,
)

LOOP_ORDER = ['LIC-100', 'TIC-100', 'FIC-100', 'FIC-101', 'FIC-102']

PLANT_INPUTS = [
    'biodiesel_reactor.c_TG_in',
    'biodiesel_reactor.T_oil',
    'biodiesel_reactor.c_MeOH_in',
    'biodiesel_reactor.T_MeOH',
    'biodiesel_reactor.c_Cat_in',
    'biodiesel_reactor.c_Water_in',
    'biodiesel_reactor.T_NaOH',
    'biodiesel_reactor.T_coolant_in',
]

PLANT_OUTPUTS = [
    'biodiesel_reactor.h',
    'biodiesel_reactor.c_TG',
    'biodiesel_reactor.c_MeOH',
    'biodiesel_reactor.c_ME',
    'biodiesel_reactor.c_DG',
    'biodiesel_reactor.c_MG',
    'biodiesel_reactor.c_Gly',
    'biodiesel_reactor.c_Cat',
    'biodiesel_reactor.c_Water',
    'biodiesel_reactor.T',
    'biodiesel_reactor.T_coolant',
]

LOOP_METADATA = {
    'LIC-100': {
        'controller': 'LC-100',
        'sensor': 'LT-100',
        'actuator': 'LV-100',
        'setpoint': 'LSP-100',
        'plant_pv': 'biodiesel_reactor.h',
        'plant_mv': 'biodiesel_reactor.f_FAME',
    },
    'TIC-100': {
        'controller': 'TC-100',
        'sensor': 'TT-100',
        'actuator': 'TV-100',
        'setpoint': 'TSP-100',
        'plant_pv': 'biodiesel_reactor.T',
        'plant_mv': 'biodiesel_reactor.f_coolant',
    },
    'FIC-100': {
        'controller': 'FC-100',
        'sensor': 'FT-100',
        'actuator': 'FV-100',
        'setpoint': 'FSP-100',
        'plant_pv': 'FV-100.F',
        'plant_mv': 'biodiesel_reactor.f_oil',
    },
    'FIC-101': {
        'controller': 'FC-101',
        'sensor': 'FT-101',
        'actuator': 'FV-101',
        'setpoint': 'FSP-101',
        'plant_pv': 'FV-101.F',
        'plant_mv': 'biodiesel_reactor.f_MeOH',
    },
    'FIC-102': {
        'controller': 'FC-102',
        'sensor': 'FT-102',
        'actuator': 'FV-102',
        'setpoint': 'FSP-102',
        'plant_pv': 'FV-102.F',
        'plant_mv': 'biodiesel_reactor.f_NaOH',
    },
}


@dataclass
class LoopRuntimeBlock:
    """A single loop block under the top-level plant layer."""

    loop_id: str
    mode: str
    systems: list[Any]
    connections: list[list[str]]
    inputs: list[str]
    outputs: list[str]


def _normalize_loop_modes(
    loop_modes: Mapping[str, str] | None,
) -> dict[str, str]:
    normalized = dict.fromkeys(LOOP_ORDER, 'automatic')
    if not loop_modes:
        return normalized

    for loop, mode in loop_modes.items():
        if loop not in normalized:
            valid = ', '.join(LOOP_ORDER)
            raise ValueError(f"Unknown biodiesel control loop '{loop}'. Valid: {valid}")

        mode_key = str(mode).strip().lower()
        if mode_key not in {'automatic', 'manual', 'off'}:
            raise ValueError(
                f"Invalid mode '{mode}' for loop '{loop}'. Use 'automatic', 'manual', or 'off'."
            )

        normalized[loop] = mode_key

    return normalized


def _build_loop_block(loop_id: str, mode: str, Ts: float) -> LoopRuntimeBlock:
    """Create a per-loop runtime block interfacing with the top-level plant."""
    meta = LOOP_METADATA[loop_id]

    if mode == 'off':
        return LoopRuntimeBlock(
            loop_id=loop_id,
            mode=mode,
            systems=[],
            connections=[],
            inputs=[],
            outputs=[],
        )

    actuator = ActuatorSystem(**ACTUATOR_PARAMS[loop_id], dt=Ts)
    sensor = SensorTransmitterSystem(**SENSOR_TRANSMITTER_PARAMS[loop_id], dt=Ts)

    systems: list[Any] = []
    connections = [
        [f'{meta["plant_mv"]}', f'{meta["actuator"]}.F'],
        [f'{meta["sensor"]}.PV', f'{meta["plant_pv"]}'],
    ]
    inputs: list[str] = []
    outputs: list[str] = []

    if mode == 'automatic':
        controller = ControllerSystem(**CONTROLLER_PARAMS[loop_id], dt=Ts)
        setpoint = SetPointSystem(**SETPOINT_PARAMS[loop_id], dt=Ts)

        systems.extend([controller.system, setpoint.system])
        connections.extend(
            [
                [f'{meta["actuator"]}.M', f'{meta["controller"]}.M'],
                [f'{meta["controller"]}.C', f'{meta["sensor"]}.C'],
                [f'{meta["controller"]}.R', f'{meta["setpoint"]}.R'],
            ]
        )
        inputs.extend(
            [
                f'{meta["controller"]}.Kc',
                f'{meta["controller"]}.tauI',
                f'{meta["controller"]}.tauD',
                f'{meta["setpoint"]}.SP',
            ]
        )
        outputs.extend(
            [
                f'{meta["controller"]}.M',
                f'{meta["setpoint"]}.R',
            ]
        )
    else:
        inputs.append(f'{meta["actuator"]}.M')

    systems.extend([actuator.system, sensor.system])
    outputs.extend([f'{meta["sensor"]}.C', f'{meta["actuator"]}.F'])

    return LoopRuntimeBlock(
        loop_id=loop_id,
        mode=mode,
        systems=systems,
        connections=connections,
        inputs=inputs,
        outputs=outputs,
    )


def build_biodiesel_closed_loop_system(
    Ts: float,
    loop_modes: Mapping[str, str] | None = None,
):
    """Build Biodiesel control system with per-loop auto/manual modes.

    Parameters
    ----------
    Ts : float
        Simulation sample time.
    loop_modes : Mapping[str, str] | None, optional
        Optional per-loop mode selection. Supported keys:
        LIC-100, TIC-100, FIC-100, FIC-101, FIC-102.
        Mode values: 'automatic' or 'manual'.

    Notes
    -----
    - If a loop is 'automatic', controller + setpoint connect to actuator.
    - If a loop is 'manual', the actuator MV input is exposed as '<ACT>.M'.
    - If a loop is 'off', no loop devices are connected; plant MV exposed.
    - Default behavior (loop_modes=None) keeps all loops in automatic mode.
    """

    loop_mode_map = _normalize_loop_modes(loop_modes)

    # Top level: plant layer
    plant = BiodieselReactorSystem(**PROCESS_PARAMS, dt=Ts)

    # Second level: loop blocks that exchange signals with the plant layer.
    loop_blocks = [
        _build_loop_block(loop_id=loop_id, mode=loop_mode_map[loop_id], Ts=Ts)
        for loop_id in LOOP_ORDER
    ]

    system_list = [plant.system]
    connections: list[list[str]] = []
    inplist = list(PLANT_INPUTS)
    outlist = list(PLANT_OUTPUTS)

    for block in loop_blocks:
        system_list.extend(block.systems)
        connections.extend(block.connections)
        inplist.extend(block.inputs)
        outlist.extend(block.outputs)

    system = build_interconnected_system(
        syslist=system_list,
        connections=connections,
        inplist=inplist,
        outlist=outlist,
        name='Biodiesel_ControllerSystem',
    )

    return system, inplist, outlist
