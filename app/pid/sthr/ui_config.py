# app/pid/sthr/ui_config.py

"""UI display configuration for the STHR (Steam Tank Heated Reactor) case.

Contains only data consumed by the app layer (NiceGUI components, SVG
drawings, controller modals). No engine, no gateway, no services.

Symbols
-------
PLANT_PARAMS
    Physical constants used to seed the SVG display before the first
    engine step arrives.
INITIAL_CONDITIONS
    Signal initial values used for SVG display seeding.
SIGNALS_CONFIG
    Per-signal label, unit, colour, and range for the data-logger chart.
DISPLAY_MAP
    SVG element id → {signal, unit} mapping used by the drawing module
    and the hub factory seed.
CONTROLLER_DRAWER_CONFIG
    Per-SVG-card id → {label, params[]} used by ControllerModal /
    FaceplateSpec to populate slider ranges and drawer titles.
"""

# ── Plant Parameters (display seed only) ──────────────────────────────────
PLANT_PARAMS = {
    'rho': 68.0,
    'Cp': 0.80,
    'V': 120.0,
    'A': 241.5,
    'Cm': 265.68,
    'U': 2.1,
    'lamb': 966.0,
}

# ── Initial Conditions (display seed only) ─────────────────────────────────
INITIAL_CONDITIONS = {
    'T': 150.0,
    'Ts': 230.0,
    'Tm': 150.0,
    'SP': 150.0,
    'F': 15.0,
    'Ti': 100.0,
    'W': 42.23,
    'vp': 82.3,
    'I': 82.3,
    'D': 50.0,
    'C': 50.0,
    'M': 82.3,
    'R': 50.0,
    'V': 120.0,
}

# ── Signal Definitions (chart colours + ranges) ────────────────────────────
SIGNALS_CONFIG = {
    'T': {
        'label': 'Tank Temp',
        'unit': '°F',
        'color': '#FF6B6B',
        'low': 100,
        'high': 200,
    },
    'Ts': {
        'label': 'Coil Temp',
        'unit': '°F',
        'color': '#FFA726',
        'low': 150,
        'high': 400,
    },
    'C': {
        'label': 'Transmitter',
        'unit': '%TO',
        'color': '#42A5F5',
        'low': 0,
        'high': 100,
    },
    'M': {
        'label': 'Controller Out',
        'unit': '%CO',
        'color': '#AB47BC',
        'low': 0,
        'high': 100,
    },
    'W': {
        'label': 'Steam Flow',
        'unit': 'lb/min',
        'color': '#66BB6A',
        'low': 0,
        'high': 84.4,
    },
    'R': {
        'label': 'Reference',
        'unit': '%',
        'color': '#FFEE58',
        'low': 0,
        'high': 100,
    },
    'vp': {
        'label': 'Valve Pos',
        'unit': '%vp',
        'color': '#26C6DA',
        'low': 0,
        'high': 100,
    },
    'SP': {
        'label': 'Set Point',
        'unit': '°F',
        'color': '#FFEE58',
        'low': 0,
        'high': 100,
    },
}

# ── Display Map: SVG element id → signal key + display unit ───────────────
DISPLAY_MAP = {
    'fi-100': {'signal': 'W', 'unit': 'lb/min'},
    'fi-101': {'signal': 'F', 'unit': 'ft³/min'},
    'tic-100': {'signal': 'T', 'unit': '°F'},
    'ti-100': {'signal': 'Ti', 'unit': '°F'},
    'li-100': {'signal': 'V', 'unit': 'ft³'},
    'fi-102': {'signal': 'F', 'unit': 'ft³/min'},
    'vp-100': {'signal': 'vp', 'unit': '%'},
}

# ── Controller Drawer Config ───────────────────────────────────────────────
# Maps each clickable SVG card id → drawer title + tunable params.
# 'field' is the local store key the modal uses (UI-only, no engine).
CONTROLLER_DRAWER_CONFIG = {
    'tic-100': {
        'label': 'TIC-100 — Temperature Controller',
        'params': [
            {
                'key': 'sp',
                'label': 'Set Point (°F)',
                'field': 'sp',
                'min': 50.0,
                'max': 300.0,
                'step': 0.1,
            },
            {
                'key': 'kc',
                'label': 'Gain (Kc)',
                'field': 'kc',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
            {
                'key': 'tau_i',
                'label': 'Integral Time (τI) minutes',
                'field': 'tau_i',
                'min': 0.01,
                'max': 100.0,
                'step': 0.01,
            },
            {
                'key': 'tau_d',
                'label': 'Derivative Time (τD) minutes',
                'field': 'tau_d',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
        ],
    },
    'fi-100': {
        'label': 'FI-100 — Steam Flow Indicator',
        'params': [
            {
                'key': 'sp',
                'label': 'Steam Flow Rate (lb/min)',
                'field': 'steam_flow',
                'min': 0.0,
                'max': 60.0,
                'step': 0.1,
            },
            {
                'key': 'pv',
                'label': 'PV',
                'field': 'fi100_pv',
                'min': 0.0,
                'max': 60.0,
                'step': 0.1,
            },
        ],
    },
    'fi-101': {
        'label': 'FI-101 — Feed Flow Indicator',
        'params': [
            {
                'key': 'feed_flow',
                'label': 'Feed Flow Rate (ft³/min)',
                'field': 'feed_flow',
                'min': 0.0,
                'max': 25.0,
                'step': 0.1,
            },
        ],
    },
    'ti-100': {
        'label': 'TI-100 — Feed Temperature Indicator',
        'params': [
            {
                'key': 'feed_temp',
                'label': 'Feed Temperature (°F)',
                'field': 'feed_temp',
                'min': 50.0,
                'max': 200.0,
                'step': 0.1,
            },
        ],
    },
    'li-100': {
        'label': 'LI-100 — Level Indicator',
        'params': [],
    },
    'fi-102': {
        'label': 'FI-102 — Product Flow Indicator',
        'params': [
            {
                'key': 'pv',
                'label': 'PV',
                'field': 'fi102_pv',
                'min': 0.0,
                'max': 25.0,
                'step': 0.1,
            },
        ],
    },
    'vp-100': {
        'label': 'VP-100 — Valve Position',
        'params': [],
    },
}
