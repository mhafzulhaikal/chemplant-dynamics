# systems/configs/biodiesel_config.py

PROCESS_PARAMS = {
    # oil stream properties
    'rho_oil': 884.72,
    'Cp_oil': 0.4454,
    # methanol stream properties
    'rho_MeOH': 792.92,
    'Cp_MeOH': 0.6734,
    # catalyst stream properties
    'rho_NaOH': 1041.12,
    'Cp_NaOH': 0.8511,
    # product stream properties
    'rho': 792.77,
    'Cp': 0.5234,
    # reactor parameters
    'Dr': 1.219,
    'Lr': 3.0,
    # reaction parameters
    'R': 1.987,
    'To': 323.15,
    'Hrxn1': -14379.67807351148,  # kcal/kmol
    'Hrxn2': -237.28589845450915,  # kcal/kmol
    'Hrxn3': -12351.943870983516,  # kcal/kmol
    # kinetic parameters
    'k1_f': 0.02311,
    'k1_r': 0.001867,
    'k2_f': 0.10659,
    'k2_r': 0.002217,
    'k3_f': 0.05754,
    'k3_r': 0.000267,
    'E1_f': 13500,
    'E1_r': 10300,
    'E2_f': 17400,
    'E2_r': 16200,
    'E3_f': 6200,
    'E3_r': 11900,
    # heat transfer parameters
    'UA': 0.3771,
    'V_coolant': 0.3607,
    # cooling fluid properties
    'rho_coolant': 998.0,
    'Cp_coolant': 1.0,
}


SENSOR_TRANSMITTER_PARAMS = {
    'LIC-100': {
        'name': 'LT-100',
        'hi': 3.0,
        'low': 0.0,
        'tauT': 0.0,
    },
    'FIC-100': {
        'name': 'FT-100',
        'hi': 6.5935e-04,
        'low': 0.0,
        'tauT': 0.0,
    },
    'FIC-101': {
        'name': 'FT-101',
        'hi': 1.6675e-04,
        'low': 0.0,
        'tauT': 0.0,
    },
    'FIC-102': {
        'name': 'FT-102',
        'hi': 2.6681e-05,
        'low': 0.0,
        'tauT': 0.0,
    },
    'TIC-100': {
        'name': 'TT-100',
        'hi': 368.15,
        'low': 298.15,
        'tauT': 45.0,
    },
}


ACTUATOR_PARAMS = {
    'LIC-100': {
        'name': 'LV-100',
        'tauV': 12.0,
        'f_max': 9.3764e-04,
        'vp_min': 0.0,
        'vp_max': 100.0,
        'valve_type': 'linear',
        'valve_action': 'FC',
    },
    'FIC-100': {
        'name': 'FV-100',
        'tauV': 12.0,
        'f_max': 6.5935e-04,
        'vp_min': 0.0,
        'vp_max': 100.0,
        'valve_type': 'linear',
        'valve_action': 'FC',
    },
    'FIC-101': {
        'name': 'FV-101',
        'tauV': 12.0,
        'f_max': 1.6675e-04,
        'vp_min': 0.0,
        'vp_max': 100.0,
        'valve_type': 'linear',
        'valve_action': 'FC',
    },
    'FIC-102': {
        'name': 'FV-102',
        'tauV': 12.0,
        'f_max': 2.6681e-05,
        'vp_min': 0.0,
        'vp_max': 100.0,
        'valve_type': 'linear',
        'valve_action': 'FC',
    },
    'TIC-100': {
        'name': 'TV-100',
        'tauV': 12.0,
        'f_max': 7.5572e-04,
        'vp_min': 0.0,
        'vp_max': 100.0,
        'valve_type': 'linear',
        'valve_action': 'FO',
    },
}


CONTROLLER_PARAMS = {
    'LIC-100': {
        'name': 'LC-100',
        'bias': 50.0,
        'mode': 'AUTO',
        'acting': 'DIRECT',
    },
    'TIC-100': {
        'name': 'TC-100',
        'bias': 50.0,
        'mode': 'AUTO',
        'acting': 'REVERSE',
    },
    'FIC-100': {
        'name': 'FC-100',
        'bias': 50.0,
        'mode': 'AUTO',
        'acting': 'REVERSE',
    },
    'FIC-101': {
        'name': 'FC-101',
        'bias': 50.0,
        'mode': 'AUTO',
        'acting': 'REVERSE',
    },
    'FIC-102': {
        'name': 'FC-102',
        'bias': 50.0,
        'mode': 'AUTO',
        'acting': 'REVERSE',
    },
}


SETPOINT_PARAMS = {
    'LIC-100': {
        'name': 'LSP-100',
        'hi': 3.0,
        'low': 0.0,
    },
    'FIC-100': {
        'name': 'FSP-100',
        'hi': 6.5935e-04,
        'low': 0.0,
    },
    'FIC-101': {
        'name': 'FSP-101',
        'hi': 1.6675e-04,
        'low': 0.0,
    },
    'FIC-102': {
        'name': 'FSP-102',
        'hi': 2.6681e-05,
        'low': 0.0,
    },
    'TIC-100': {
        'name': 'TSP-100',
        'hi': 368.15,
        'low': 298.15,
    },
}
