# cases/biodiesel/config.py

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

SIMULATION_PARAMS = {
    'Ts': 0.5,  # seconds
    'time_end': float('inf'),
    'time_unit': 'seconds',
    'acceleration': 1.0,
    'real_time': False,
    'timeseries_buffer': 100,
}

CONTROLLER_MODE = {
    'Mode': 'Automatic',
    # Optional override example:
    # "LoopModes": {"TIC-100": "manual", "FIC-100": "automatic"}
}

LOOP_ORDER = ('LIC-100', 'TIC-100', 'FIC-100', 'FIC-101', 'FIC-102')

LOOP_SIGNAL_MAP = {
    'LIC-100': {
        'controller': 'LC-100',
        'setpoint': 'LSP-100',
        'actuator': 'LV-100',
        'plant_mv': 'biodiesel_reactor.f_FAME',
    },
    'TIC-100': {
        'controller': 'TC-100',
        'setpoint': 'TSP-100',
        'actuator': 'TV-100',
        'plant_mv': 'biodiesel_reactor.f_coolant',
    },
    'FIC-100': {
        'controller': 'FC-100',
        'setpoint': 'FSP-100',
        'actuator': 'FV-100',
        'plant_mv': 'biodiesel_reactor.f_oil',
    },
    'FIC-101': {
        'controller': 'FC-101',
        'setpoint': 'FSP-101',
        'actuator': 'FV-101',
        'plant_mv': 'biodiesel_reactor.f_MeOH',
    },
    'FIC-102': {
        'controller': 'FC-102',
        'setpoint': 'FSP-102',
        'actuator': 'FV-102',
        'plant_mv': 'biodiesel_reactor.f_NaOH',
    },
}

DEFAULT_LOOP_MODE = dict.fromkeys(LOOP_ORDER, 'automatic')

REFERENCE_INPUT = {
    'LSP-100.SP': 1.50,
    'TSP-100.SP': 333.15,
    'FSP-100.SP': 3.29675e-04,
    'FSP-101.SP': 8.33750e-05,
    'FSP-102.SP': 1.33405e-05,
}

CONTROLLER_INPUT = {
    'LC-100.Kc': 77.80,
    'LC-100.tauI': 0.0,
    'LC-100.tauD': 0.0,
    'TC-100.Kc': 10.34,
    'TC-100.tauI': 1070.07,
    'TC-100.tauD': 267.52,
    'FC-100.Kc': 0.33,
    'FC-100.tauI': 12.0,
    'FC-100.tauD': 0.0,
    'FC-101.Kc': 0.33,
    'FC-101.tauI': 12.0,
    'FC-101.tauD': 0.0,
    'FC-102.Kc': 0.33,
    'FC-102.tauI': 12.0,
    'FC-102.tauD': 0.0,
}

CONTROLLER_STATE = {
    'LC-100.I_state': 50.0,  # steady-state controller output = bias = 50%
    'LC-100.D_state': 0.0,
    'TC-100.I_state': 80.0,
    'TC-100.D_state': 50.0,
    'FC-100.I_state': 50.0,
    'FC-100.D_state': 0.0,
    'FC-101.I_state': 50.0,
    'FC-101.D_state': 0.0,
    'FC-102.I_state': 50.0,
    'FC-102.D_state': 0.0,
}

ACTUATOR_INPUT = {
    'LV-100.M': 50.0,
    # FO valve: M=80 -> u_eff=100-80=20 -> vp=20 = same as auto steady-state
    'TV-100.M': 80.0,
    'FV-100.M': 50.0,
    'FV-101.M': 50.0,
    'FV-102.M': 50.0,
}

ACTUATOR_STATE = {
    'LV-100.vp': 50.0,
    'TV-100.vp': 20.0,
    'FV-100.vp': 50.0,
    'FV-101.vp': 50.0,
    'FV-102.vp': 50.0,
}

PLANT_INPUT = {
    'biodiesel_reactor.c_TG_in': 0.9992,
    'biodiesel_reactor.T_oil': 333.15,
    'biodiesel_reactor.c_MeOH_in': 24.7462,
    'biodiesel_reactor.T_MeOH': 298.15,
    'biodiesel_reactor.c_Cat_in': 5.2060,
    'biodiesel_reactor.c_Water_in': 46.2325,
    'biodiesel_reactor.T_NaOH': 298.15,
    'biodiesel_reactor.T_coolant_in': 298.15,
    'biodiesel_reactor.f_oil': 3.29675e-04,
    'biodiesel_reactor.f_MeOH': 8.33750e-05,
    'biodiesel_reactor.f_NaOH': 1.33405e-05,
    # LV-100 @ vp=50%: (50/100)*f_max = steady-state
    'biodiesel_reactor.f_FAME': 4.6882e-04,
    # TV-100 @ vp=20%: (20/100)*f_max = steady-state
    'biodiesel_reactor.f_coolant': 1.5114e-04,
}

SENSOR_TRANSMITTER_INPUT = {
    'LT-100.PV': 1.50,
    'TT-100.PV': 333.15,
    'FT-100.PV': 3.29675e-04,
    'FT-101.PV': 8.33750e-05,
    'FT-102.PV': 1.33405e-05,
}

SENSOR_TRANSMITTER_STATE = {
    'TT-100.PVm': 333.15,
}

PLANT_STATE = {
    'h': 1.50,
    'c_TG': 0.0142,
    'c_MeOH': 2.3760,
    'c_ME': 2.0250,
    'c_DG': 0.0055,
    'c_MG': 0.0292,
    'c_Gly': 0.6537,
    'c_Cat': 0.1481,
    'c_Water': 1.3156,
    'T': 333.15,
    'T_coolant': 323.15,
}

SCENARIO_ORDER = ('startup', 'operational', 'shutdown')

# ---------------------------------------------------------------------------
# Scenario initial states
# ---------------------------------------------------------------------------
# Each scenario defines the plant state, sensor state, controller state, and
# actuator state that will be used as x0 when the simulation is (re)started.
#
# "startup"     — reactor is empty and cold; all concentrations zero, tanks
#                 empty (h=0), temperatures at room temperature (298.15 K).
#                 Controllers reset; actuators at 50 % (neutral).
#
# "operational" — steady-state operating point (same as PLANT_STATE/etc.).
#
# "shutdown"    — same initial condition as operational; operator can then
#                 ramp inputs down from that point.
# ---------------------------------------------------------------------------

SCENARIO_INITIAL_STATES: dict[str, dict[str, float]] = {
    'startup': {
        # Plant: empty reactor, all concentrations zero, temperatures at 298.15
        # K
        'biodiesel_reactor.h': 0.0,
        'biodiesel_reactor.c_TG': 0.0,
        'biodiesel_reactor.c_MeOH': 0.0,
        'biodiesel_reactor.c_ME': 0.0,
        'biodiesel_reactor.c_DG': 0.0,
        'biodiesel_reactor.c_MG': 0.0,
        'biodiesel_reactor.c_Gly': 0.0,
        'biodiesel_reactor.c_Cat': 0.0,
        'biodiesel_reactor.c_Water': 0.0,
        'biodiesel_reactor.T': 298.15,  # room temperature
        'biodiesel_reactor.T_coolant': 298.15,
        # Sensor: PV at room / zero
        'TT-100.PVm': 298.15,
        # Controllers: reset (I_state = 0, D_state = 0)
        'LC-100.I_state': 0.0,
        'LC-100.D_state': 0.0,
        'TC-100.I_state': 0.0,
        'TC-100.D_state': 0.0,
        'FC-100.I_state': 0.0,
        'FC-100.D_state': 0.0,
        'FC-101.I_state': 0.0,
        'FC-101.D_state': 0.0,
        'FC-102.I_state': 0.0,
        'FC-102.D_state': 0.0,
        # Actuators: 0 % off position
        'LV-100.vp': 0.0,
        'TV-100.vp': 0.0,
        'FV-100.vp': 0.0,
        'FV-101.vp': 0.0,
        'FV-102.vp': 0.0,
    },
    'operational': {
        # Plant: steady-state operating point
        'biodiesel_reactor.h': float(PLANT_STATE['h']),
        'biodiesel_reactor.c_TG': float(PLANT_STATE['c_TG']),
        'biodiesel_reactor.c_MeOH': float(PLANT_STATE['c_MeOH']),
        'biodiesel_reactor.c_ME': float(PLANT_STATE['c_ME']),
        'biodiesel_reactor.c_DG': float(PLANT_STATE['c_DG']),
        'biodiesel_reactor.c_MG': float(PLANT_STATE['c_MG']),
        'biodiesel_reactor.c_Gly': float(PLANT_STATE['c_Gly']),
        'biodiesel_reactor.c_Cat': float(PLANT_STATE['c_Cat']),
        'biodiesel_reactor.c_Water': float(PLANT_STATE['c_Water']),
        'biodiesel_reactor.T': float(PLANT_STATE['T']),
        'biodiesel_reactor.T_coolant': float(PLANT_STATE['T_coolant']),
        # Sensor
        'TT-100.PVm': float(SENSOR_TRANSMITTER_STATE['TT-100.PVm']),
        # Controllers: tuned steady-state
        'LC-100.I_state': float(CONTROLLER_STATE['LC-100.I_state']),
        'LC-100.D_state': float(CONTROLLER_STATE['LC-100.D_state']),
        'TC-100.I_state': float(CONTROLLER_STATE['TC-100.I_state']),
        'TC-100.D_state': float(CONTROLLER_STATE['TC-100.D_state']),
        'FC-100.I_state': float(CONTROLLER_STATE['FC-100.I_state']),
        'FC-100.D_state': float(CONTROLLER_STATE['FC-100.D_state']),
        'FC-101.I_state': float(CONTROLLER_STATE['FC-101.I_state']),
        'FC-101.D_state': float(CONTROLLER_STATE['FC-101.D_state']),
        'FC-102.I_state': float(CONTROLLER_STATE['FC-102.I_state']),
        'FC-102.D_state': float(CONTROLLER_STATE['FC-102.D_state']),
        # Actuators: steady-state valve positions
        'LV-100.vp': float(ACTUATOR_STATE['LV-100.vp']),
        'TV-100.vp': float(ACTUATOR_STATE['TV-100.vp']),
        'FV-100.vp': float(ACTUATOR_STATE['FV-100.vp']),
        'FV-101.vp': float(ACTUATOR_STATE['FV-101.vp']),
        'FV-102.vp': float(ACTUATOR_STATE['FV-102.vp']),
    },
}
# Shutdown starts from the same conditions as operational
SCENARIO_INITIAL_STATES['shutdown'] = dict(SCENARIO_INITIAL_STATES['operational'])


STARTUP_ACTUATOR_INPUT = {
    # Direct acting valves: M=0 -> vp=0
    'LV-100.M': 0.0,
    'FV-100.M': 0.0,
    'FV-101.M': 0.0,
    'FV-102.M': 0.0,
    # TV-100 is reverse/fail-open style based on existing comment:
    # M=80 -> u_eff=100-80=20 -> vp=20
    # Therefore M=100 -> u_eff=0 -> vp=0
    'TV-100.M': 100.0,
}


def initial_states_for_scenario(scenario: str | None) -> dict[str, float]:
    """Return initial state dict for the given scenario name.

    Names are matched case-insensitively. Falls back to 'operational'
    if the scenario is unknown or None.
    """
    key = str(scenario or 'operational').strip().lower()
    return dict(SCENARIO_INITIAL_STATES.get(key, SCENARIO_INITIAL_STATES['operational']))


CASE_RUNTIME = CaseRuntimeConfig(
    case_name='biodiesel',
    supported_modes=('automatic', 'manual', 'off'),
    default_mode='automatic',
    time_unit='seconds',
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
    """Resolve per-loop automatic/manual/off mode settings from config.

    Global case mode sets the default for all loops, and LoopModes can override
    specific loops.
    """
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

    for loop, mode in configured.items():
        if loop not in resolved:
            continue
        mode_key = str(mode).strip().lower()
        if mode_key in {'automatic', 'manual', 'off'}:
            resolved[loop] = mode_key

    return resolved  # type: ignore


def _mixed_inputs_from_loop_modes(loop_modes: dict[str, str]) -> dict[str, float]:
    _pi = PLANT_INPUT
    inputs: dict[str, float] = {
        'biodiesel_reactor.c_TG_in': float(_pi.get('biodiesel_reactor.c_TG_in', 0.9992)),
        'biodiesel_reactor.T_oil': float(_pi.get('biodiesel_reactor.T_oil', 333.15)),
        'biodiesel_reactor.c_MeOH_in': float(_pi.get('biodiesel_reactor.c_MeOH_in', 24.7462)),
        'biodiesel_reactor.T_MeOH': float(_pi.get('biodiesel_reactor.T_MeOH', 298.15)),
        'biodiesel_reactor.c_Cat_in': float(_pi.get('biodiesel_reactor.c_Cat_in', 5.2060)),
        'biodiesel_reactor.c_Water_in': float(_pi.get('biodiesel_reactor.c_Water_in', 46.2325)),
        'biodiesel_reactor.T_NaOH': float(_pi.get('biodiesel_reactor.T_NaOH', 298.15)),
        'biodiesel_reactor.T_coolant_in': float(_pi.get('biodiesel_reactor.T_coolant_in', 298.15)),
    }

    for loop in LOOP_ORDER:
        meta = LOOP_SIGNAL_MAP[loop]
        if loop_modes.get(loop, 'automatic') == 'automatic':
            sp = f'{meta["setpoint"]}.SP'
            kc = f'{meta["controller"]}.Kc'
            tau_i = f'{meta["controller"]}.tauI'
            tau_d = f'{meta["controller"]}.tauD'
            inputs[sp] = float(REFERENCE_INPUT.get(sp, 0.0))
            inputs[kc] = float(CONTROLLER_INPUT.get(kc, 2.0))
            inputs[tau_i] = float(CONTROLLER_INPUT.get(tau_i, 30.0))
            inputs[tau_d] = float(CONTROLLER_INPUT.get(tau_d, 5.0))
        elif loop_modes.get(loop, 'automatic') == 'manual':
            mv = f'{meta["actuator"]}.M'
            inputs[mv] = float(ACTUATOR_INPUT.get(mv, 50.0))
        elif loop_modes.get(loop, 'automatic') == 'off':
            pass

    return inputs


def default_inputs_for_mode(mode: str | None) -> dict[str, float]:
    mode_key = normalize_mode(mode, CONTROLLER_MODE.get('Mode', 'Off'))
    if mode_key in {'automatic', 'manual', 'off'}:
        return _mixed_inputs_from_loop_modes(resolve_loop_modes(mode_key))
    return {}


def default_state_vector() -> list[float]:
    return [
        float(PLANT_STATE['h']),
        float(PLANT_STATE['c_TG']),
        float(PLANT_STATE['c_MeOH']),
        float(PLANT_STATE['c_ME']),
        float(PLANT_STATE['c_DG']),
        float(PLANT_STATE['c_MG']),
        float(PLANT_STATE['c_Gly']),
        float(PLANT_STATE['c_Cat']),
        float(PLANT_STATE['c_Water']),
        float(PLANT_STATE['T']),
        float(PLANT_STATE['T_coolant']),
    ]


def default_initial_states() -> dict[str, float]:
    """Return initial states keyed by 'sysname.statename' for x0 lookup.

    Plant states are prefixed with 'biodiesel_reactor.' to match the
    state_label format produced by python-control InterconnectedSystem.
    All other subsystem states already use the correct 'sysname.statename'
    format in the config dicts.
    """
    states: dict[str, float] = {}
    for key, val in PLANT_STATE.items():
        states[f'biodiesel_reactor.{key}'] = float(val)
    states.update(SENSOR_TRANSMITTER_STATE)
    states.update(CONTROLLER_STATE)
    states.update(ACTUATOR_STATE)
    return states


def default_inputs_for_scenario_mode(
    scenario: str | None,
    mode: str | None,
) -> dict[str, float]:
    """
    Return default external inputs using both scenario and mode.

    This is needed because scenario initial states only define x0.
    Actuator commands must also be consistent with the scenario.
    """
    scenario_key = str(scenario or 'operational').strip().lower()
    mode_key = normalize_mode(mode, CONTROLLER_MODE.get('Mode', 'Off'))

    values = default_inputs_for_mode(mode_key)

    if scenario_key == 'startup':
        # Force startup actuator commands to match startup actuator states.
        #
        # Without this, TV-100 may fall back to
        # ACTUATOR_INPUT["TV-100.M"] = 80, which produces vp=20.
        values.update(STARTUP_ACTUATOR_INPUT)

    return {name: float(value) for name, value in values.items()}


def prepare_external_inputs(
    mode: str | None,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    return merge_input_dicts(default_inputs_for_mode(mode), overrides)


__all__ = [
    'ACTUATOR_INPUT',
    'ACTUATOR_STATE',
    'CASE_RUNTIME',
    'CONTROLLER_INPUT',
    'CONTROLLER_MODE',
    'CONTROLLER_STATE',
    'DEFAULT_LOOP_MODE',
    'LOOP_ORDER',
    'LOOP_SIGNAL_MAP',
    'PLANT_INPUT',
    'PLANT_STATE',
    'REFERENCE_INPUT',
    'SCENARIO_INITIAL_STATES',
    'SCENARIO_ORDER',
    'SENSOR_TRANSMITTER_INPUT',
    'SENSOR_TRANSMITTER_STATE',
    'SIMULATION_PARAMS',
    'STARTUP_ACTUATOR_INPUT',
    'default_initial_states',
    'default_input_values',
    'default_inputs_for_mode',
    'default_inputs_for_scenario_mode',
    'default_state_vector',
    'from_minutes',
    'normalize_mode',
    'initial_states_for_scenario',
    'normalize_time_unit',
    'prepare_external_inputs',
    'resolve_loop_modes',
    'time_unit_short_label',
    'to_minutes',
]
