from __future__ import annotations

from collections.abc import Mapping

from models import (
    ActuatorSystem,
    ControllerSystem,
    SensorTransmitterSystem,
    SetPointSystem,
    STHRSystem,
)
from systems.builders.common import build_interconnected_system
from systems.configs.sthr_config import (
    ACTUATOR_PARAMS,
    CONTROLLER_PARAMS,
    PROCESS_PARAMS,
    SENSOR_TRANSMITTER_PARAMS,
    SETPOINT_PARAMS,
)

LOOP_ID = 'TIC-100'

PLANT_INPUTS = ['STHR.F', 'STHR.Ti']
PLANT_OUTPUTS = ['STHR.T', 'STHR.Ts']


def _normalize_loop_modes(loop_modes: Mapping[str, str] | None) -> dict[str, str]:
    normalized = {LOOP_ID: 'automatic'}
    if not loop_modes:
        return normalized

    for loop, mode in loop_modes.items():
        if loop != LOOP_ID:
            raise ValueError(f"Unknown STHR control loop '{loop}'. Valid: {LOOP_ID}")

        mode_key = str(mode).strip().lower()
        if mode_key not in {'automatic', 'manual', 'off'}:
            raise ValueError(
                f"Invalid mode '{mode}' for loop '{loop}'. Use 'automatic', 'manual', or 'off'."
            )

        normalized[loop] = mode_key

    return normalized


def build_sthr_closed_loop_system(
    Ts,
    loop_modes: Mapping[str, str] | None = None,
):
    """Build STHR control system with per-loop automatic/manual/off support."""

    loop_mode_map = _normalize_loop_modes(loop_modes)
    mode = loop_mode_map[LOOP_ID]

    plant = STHRSystem(**PROCESS_PARAMS, dt=Ts)
    sensor = SensorTransmitterSystem(**SENSOR_TRANSMITTER_PARAMS[LOOP_ID], dt=Ts)

    systems = [plant.system, sensor.system]
    connections = [['TT-100.PV', 'STHR.T']]
    inplist = list(PLANT_INPUTS)
    outlist = [*PLANT_OUTPUTS, 'TT-100.C']

    if mode == 'automatic':
        actuator = ActuatorSystem(**ACTUATOR_PARAMS[LOOP_ID], dt=Ts)
        controller = ControllerSystem(**CONTROLLER_PARAMS[LOOP_ID], dt=Ts)
        setpoint = SetPointSystem(**SETPOINT_PARAMS[LOOP_ID], dt=Ts)

        systems.extend([controller.system, actuator.system, setpoint.system])
        connections.extend(
            [
                ['TC-100.R', 'TSP-100.R'],
                ['TC-100.C', 'TT-100.C'],
                ['TV-100.M', 'TC-100.M'],
                ['STHR.W', 'TV-100.F'],
            ]
        )

        inplist.extend(['TSP-100.SP', 'TC-100.Kc', 'TC-100.tauI', 'TC-100.tauD'])
        outlist.extend(['TC-100.M', 'TV-100.F', 'TSP-100.R'])

    elif mode == 'manual':
        actuator = ActuatorSystem(**ACTUATOR_PARAMS[LOOP_ID], dt=Ts)

        systems.append(actuator.system)
        connections.append(['STHR.W', 'TV-100.F'])

        inplist.append('TV-100.M')
        outlist.append('TV-100.F')

    else:
        # Off mode: loop control path is disabled. Plant inputs (MVs) default
        # to 0.
        pass

    clsys = build_interconnected_system(
        syslist=systems,
        connections=connections,
        inplist=inplist,
        outlist=outlist,
        name='STHR_ControllerSystem',
    )

    return clsys, inplist, outlist


def build_sthr_open_loop_system(Ts):
    """Compatibility wrapper for manual loop mode."""
    return build_sthr_closed_loop_system(Ts, loop_modes={LOOP_ID: 'manual'})


def build_sthr_off_system(Ts):
    """Compatibility wrapper for off loop mode."""
    return build_sthr_closed_loop_system(Ts, loop_modes={LOOP_ID: 'off'})
