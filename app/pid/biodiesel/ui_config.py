# app/pid/biodiesel/ui_config.py

"""UI display configuration for the Biodiesel reactor case.

Contains only data consumed by the app layer (NiceGUI components, SVG
drawings, controller modals). No engine, no gateway, no services.

Symbols
-------
CONTROLLER_DRAWER_CONFIG
    Per-SVG-card id → {label, params[]} used by ControllerModal /
    FaceplateSpec to populate slider ranges and drawer titles.

    Tags that appear in both STHR and Biodiesel (e.g. TIC-100, TI-100,
    FI-100, FI-101) are redefined here with Biodiesel-specific ranges and
    units so the two cases never collide.
"""

# ── Controller Drawer Config ───────────────────────────────────────────────
# Maps each clickable SVG card id → drawer title + tunable params.
# 'field' is the local store key the modal uses (UI-only, no engine).
CONTROLLER_DRAWER_CONFIG = {
    # ── Tunable controllers ────────────────────────────────────────────────
    'lic-100': {
        'label': 'LIC-100 — Level Controller',
        'params': [
            {
                'key': 'sp',
                'label': 'Set Point (m)',
                'field': 'lic_sp',
                'min': 0.0,
                'max': 2.0,
                'step': 0.01,
            },
            {
                'key': 'kc',
                'label': 'Gain (Kc)',
                'field': 'lic_kc',
                'min': 0.0,
                'max': 200.0,
                'step': 0.01,
            },
            {
                'key': 'tau_i',
                'label': 'Integral Time (τI) seconds',
                'field': 'lic_tau_i',
                'min': 0.0,
                'max': 100.0,
                'step': 0.01,
            },
            {
                'key': 'tau_d',
                'label': 'Derivative Time (τD) seconds',
                'field': 'lic_tau_d',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
        ],
    },
    'tic-100': {
        'label': 'TIC-100 — Temperature Controller',
        'params': [
            {
                'key': 'sp',
                'label': 'Set Point (K)',
                'field': 'tic_sp',
                'min': 290.0,
                'max': 370.0,
                'step': 0.01,
            },
            {
                'key': 'kc',
                'label': 'Gain (Kc)',
                'field': 'tic_kc',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
            {
                'key': 'tau_i',
                'label': 'Integral Time (τI) seconds',
                'field': 'tic_tau_i',
                'min': 0.0,
                'max': 2000.0,
                'step': 0.01,
            },
            {
                'key': 'tau_d',
                'label': 'Derivative Time (τD) seconds',
                'field': 'tic_tau_d',
                'min': 0.0,
                'max': 500.0,
                'step': 0.01,
            },
        ],
    },
    'fic-100': {
        'label': 'FIC-100 — Oil Feed Flow',
        'params': [
            {
                'key': 'sp',
                'label': 'Set Point (m³/h)',
                'field': 'fic100_sp',
                'min': 0.0,
                'max': 1.5,
                'step': 0.01,
            },
            {
                'key': 'kc',
                'label': 'Gain (Kc)',
                'field': 'fic100_kc',
                'min': 0.0,
                'max': 10.0,
                'step': 0.01,
            },
            {
                'key': 'tau_i',
                'label': 'Integral Time (τI) seconds',
                'field': 'fic100_tau_i',
                'min': 0.0,
                'max': 100.0,
                'step': 0.01,
            },
            {
                'key': 'tau_d',
                'label': 'Derivative Time (τD) seconds',
                'field': 'fic100_tau_d',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
        ],
    },
    'fic-101': {
        'label': 'FIC-101 — Methanol Feed Flow',
        'params': [
            {
                'key': 'sp',
                'label': 'Set Point (m³/h)',
                'field': 'fic101_sp',
                'min': 0.0,
                'max': 0.4,
                'step': 0.01,
            },
            {
                'key': 'kc',
                'label': 'Gain (Kc)',
                'field': 'fic101_kc',
                'min': 0.0,
                'max': 10.0,
                'step': 0.01,
            },
            {
                'key': 'tau_i',
                'label': 'Integral Time (τI) seconds',
                'field': 'fic101_tau_i',
                'min': 0.0,
                'max': 100.0,
                'step': 0.01,
            },
            {
                'key': 'tau_d',
                'label': 'Derivative Time (τD) seconds',
                'field': 'fic101_tau_d',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
        ],
    },
    'fic-102': {
        'label': 'FIC-102 — NaOH Catalyst Feed',
        'params': [
            {
                'key': 'sp',
                'label': 'Set Point (m³/h)',
                'field': 'fic102_sp',
                'min': 0.0,
                'max': 0.075,
                'step': 0.001,
            },
            {
                'key': 'kc',
                'label': 'Gain (Kc)',
                'field': 'fic102_kc',
                'min': 0.0,
                'max': 10.0,
                'step': 0.01,
            },
            {
                'key': 'tau_i',
                'label': 'Integral Time (τI) seconds',
                'field': 'fic102_tau_i',
                'min': 0.0,
                'max': 100.0,
                'step': 0.01,
            },
            {
                'key': 'tau_d',
                'label': 'Derivative Time (τD) seconds',
                'field': 'fic102_tau_d',
                'min': 0.0,
                'max': 50.0,
                'step': 0.01,
            },
        ],
    },
    # ── Editable input indicators (boundary conditions) ────────────────────
    'ti-100': {
        'label': 'TI-100 — Oil Feed Temperature',
        'params': [
            {'key': 'sp', 'min': 290.0, 'max': 360.0, 'step': 0.1},
        ],
    },
    'ti-101': {
        'label': 'TI-101 — Methanol Feed Temperature',
        'params': [
            {'key': 'sp', 'min': 290.0, 'max': 360.0, 'step': 0.1},
        ],
    },
    'ti-102': {
        'label': 'TI-102 — NaOH Feed Temperature',
        'params': [
            {'key': 'sp', 'min': 290.0, 'max': 360.0, 'step': 0.1},
        ],
    },
    'ti-103': {
        'label': 'TI-103 — Coolant Pump Discharge',
        'params': [
            {'key': 'sp', 'min': 290.0, 'max': 360.0, 'step': 0.1},
        ],
    },
    'ti-104': {
        'label': 'TI-104 — Jacket Outlet Temperature',
        'params': [
            {'key': 'pv', 'min': 290.0, 'max': 370.0},
        ],
    },
    'fi-100': {
        'label': 'FI-100 — Coolant Flow',
        'params': [
            {'key': 'pv', 'min': 0.0, 'max': 5.0},
        ],
    },
    'fi-101': {
        'label': 'FI-101 — Product Flow',
        'params': [
            {'key': 'pv', 'min': 0.0, 'max': 2.5},
        ],
    },
    'pi-100': {
        'label': 'PI-100 — Reactor Pressure',
        'params': [
            {'key': 'pv', 'min': 0.0, 'max': 1.5},
        ],
    },
    # ── Valve positions ────────────────────────────────────────────────────
    'lv-100': {'label': 'LV-100 — Level Valve Position', 'params': []},
    'tv-100': {'label': 'TV-100 — Coolant Valve Position', 'params': []},
    'fv-100': {'label': 'FV-100 — Oil Feed Valve Position', 'params': []},
    'fv-101': {'label': 'FV-101 — Methanol Feed Valve Position', 'params': []},
    'fv-102': {'label': 'FV-102 — NaOH Feed Valve Position', 'params': []},
}
