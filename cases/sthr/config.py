from __future__ import annotations

from cases.common import (
    CaseRuntimeConfig,
    from_minutes,
    merge_input_dicts,
    normalize_mode,
    normalize_time_unit,
    time_unit_short_label,
    to_minutes,
)

# SIMULATION
SIMULATION_PARAMS = {
    'Ts': 0.01,  # minutes
    'time_end': float('inf'),
    'time_unit': 'minutes',
    # >1.0 to speed up, <1.0 to slow down, 1.0 for real-time
    'acceleration': 1.0,
    'real_time': False,
    'timeseries_backend': 'memory',
    'timeseries_csv_path': './timeseries.csv',
    'timeseries_buffer': 100,
}

# REFERENCE
REFERENCE_INPUT = {
    'TSP-100.SP': 150.0,
}

REFERENCE_OUTPUT = {
    'TSP-100.R': 50.0,
}

# CONTROLLER
CONTROLLER_MODE = {'Mode': 'Automatic'}  # Automatic, Manual, Off

LOOP_ORDER = ('TIC-100',)

LOOP_SIGNAL_MAP = {
    'TIC-100': {
        'controller': 'TC-100',
        'setpoint': 'TSP-100',
        'actuator': 'TV-100',
        'plant_mv': 'STHR.W',
    }
}

DEFAULT_LOOP_MODE = dict.fromkeys(LOOP_ORDER, 'automatic')

CONTROLLER_INPUT = {
    'TC-100.R': 50.0,
    'TC-100.C': 50.0,
    'TC-100.Kc': 6.10,
    'TC-100.tauI': 2.30,
    'TC-100.tauD': 0.58,
}

CONTROLLER_STATE = {
    'TC-100.I_state': 82.3,
    'TC-100.D_state': 50.0,
}

CONTROLLER_OUTPUT = {
    'TC-100.M': 82.3,
}

# ACTUATOR
ACTUATOR_INPUT = {
    'TV-100.M': 82.3,
}

ACTUATOR_STATE = {
    'TV-100.vp': 82.3,
}

ACTUATOR_OUTPUT = {
    'TV-100.F': 42.2,
}

# PLANT
PLANT_INPUT = {
    'STHR.W': 42.2,
    'STHR.F': 15.0,
    'STHR.Ti': 100.0,
}

PLANT_OUTPUT = {
    'STHR.T': 150.0,
    'STHR.Ts': 230.0,
}

# SENSOR-TRANSMITTER
SENSOR_TRANSMITTER_INPUT = {
    'TT-100.PV': 150.0,
}

SENSOR_TRANSMITTER_STATE = {
    'TT-100.PVm': 150.0,
}

SENSOR_TRANSMITTER_OUTPUT = {
    'TT-100.C': 50.0,
}

CASE_RUNTIME = CaseRuntimeConfig(
    case_name='sthr',
    supported_modes=('automatic', 'manual', 'off'),
    default_mode='automatic',
    time_unit='minutes',
)


def default_input_values() -> dict[str, float]:
    values: dict[str, float] = {}
    values.update(REFERENCE_INPUT)
    values.update(CONTROLLER_INPUT)
    values.update(ACTUATOR_INPUT)
    values.update(PLANT_INPUT)
    values.update(SENSOR_TRANSMITTER_INPUT)
    return {name: float(value) for name, value in values.items()}


def resolve_loop_modes(mode: str | None = None) -> dict[str, str]:
    """Resolve per-loop automatic/manual/off mode settings from config."""
    mode_key = normalize_mode(mode, CONTROLLER_MODE.get('Mode', 'Automatic'))

    if mode_key == 'manual':
        resolved = dict.fromkeys(LOOP_ORDER, 'manual')
    elif mode_key == 'off':
        resolved = dict.fromkeys(LOOP_ORDER, 'off')
    else:
        resolved = dict.fromkeys(LOOP_ORDER, 'automatic')

    configured = CONTROLLER_MODE.get('LoopModes', {})
    if not isinstance(configured, dict):
        return resolved  # type: ignore

    for loop, loop_mode in configured.items():
        if loop not in resolved:
            continue

        mode_value = str(loop_mode).strip().lower()
        if mode_value in {'automatic', 'manual', 'off'}:
            resolved[loop] = mode_value

    return resolved  # type: ignore


def _mixed_inputs_from_loop_modes(loop_modes: dict[str, str]) -> dict[str, float]:
    inputs = {
        'STHR.F': float(PLANT_INPUT.get('STHR.F', 15.0)),
        'STHR.Ti': float(PLANT_INPUT.get('STHR.Ti', 100.0)),
    }

    for loop in LOOP_ORDER:
        meta = LOOP_SIGNAL_MAP[loop]
        mode = loop_modes.get(loop, 'automatic')

        if mode == 'automatic':
            sp = f'{meta["setpoint"]}.SP'
            kc = f'{meta["controller"]}.Kc'
            tau_i = f'{meta["controller"]}.tauI'
            tau_d = f'{meta["controller"]}.tauD'
            inputs[sp] = float(REFERENCE_INPUT.get(sp, 150.0))
            inputs[kc] = float(CONTROLLER_INPUT.get(kc, 6.10))
            inputs[tau_i] = float(CONTROLLER_INPUT.get(tau_i, 2.30))
            inputs[tau_d] = float(CONTROLLER_INPUT.get(tau_d, 0.58))
        elif mode == 'manual':
            mv = f'{meta["actuator"]}.M'
            inputs[mv] = float(ACTUATOR_INPUT.get(mv, 82.3))
        elif mode == 'off':
            pass

    return inputs


def default_inputs_for_mode(mode: str | None) -> dict[str, float]:
    mode_key = normalize_mode(mode, CONTROLLER_MODE.get('Mode', 'Automatic'))
    if mode_key in {'automatic', 'manual', 'off'}:
        return _mixed_inputs_from_loop_modes(resolve_loop_modes(mode_key))
    return {}


def prepare_external_inputs(
    mode: str | None,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    return merge_input_dicts(default_inputs_for_mode(mode), overrides)


__all__ = [
    'ACTUATOR_INPUT',
    'ACTUATOR_OUTPUT',
    'ACTUATOR_STATE',
    'CASE_RUNTIME',
    'CONTROLLER_INPUT',
    'CONTROLLER_MODE',
    'CONTROLLER_OUTPUT',
    'CONTROLLER_STATE',
    'DEFAULT_LOOP_MODE',
    'LOOP_ORDER',
    'LOOP_SIGNAL_MAP',
    'PLANT_INPUT',
    'PLANT_OUTPUT',
    'REFERENCE_INPUT',
    'REFERENCE_OUTPUT',
    'SENSOR_TRANSMITTER_INPUT',
    'SENSOR_TRANSMITTER_OUTPUT',
    'SENSOR_TRANSMITTER_STATE',
    'SIMULATION_PARAMS',
    'default_input_values',
    'default_inputs_for_mode',
    'from_minutes',
    'normalize_mode',
    'normalize_time_unit',
    'prepare_external_inputs',
    'resolve_loop_modes',
    'time_unit_short_label',
    'to_minutes',
]
