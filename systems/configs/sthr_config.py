# systems/configs/sthr_config.py

PROCESS_PARAMS = {
    # sthr parameters
    'rho': 68.0,
    'Cp': 0.80,
    'V': 120.0,
    'A': 241.5,
    'Cm': 265.68,
    'U': 2.1,
    'lamb': 966.0,
}


SENSOR_TRANSMITTER_PARAMS = {'TIC-100': {'name': 'TT-100', 'hi': 200.0, 'low': 100.0, 'tauT': 0.75}}


ACTUATOR_PARAMS = {
    'TIC-100': {
        'name': 'TV-100',
        'tauV': 0.2,
        'f_max': 84.4,
        'vp_min': 0.0,
        'vp_max': 100.0,
        'valve_type': 'equal_percentage',
        'valve_action': 'FC',
    }
}


CONTROLLER_PARAMS = {
    'TIC-100': {'name': 'TC-100', 'bias': 50.0, 'mode': 'AUTO', 'acting': 'REVERSE'}
}


SETPOINT_PARAMS = {'TIC-100': {'name': 'TSP-100', 'hi': 200.0, 'low': 100.0}}
