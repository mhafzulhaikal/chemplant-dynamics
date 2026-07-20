# app/config.py

"""Global app configuration (paths, layout, shared thresholds).

This module contains only settings that apply to the entire application
regardless of which simulation case is active.

Case-specific UI configuration lives alongside each case's PID module:
- STHR     → app/pid/sthr/ui_config.py
- Biodiesel → app/pid/biodiesel/ui_config.py
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / 'static'

# ── Layout ─────────────────────────────────────────────────────────────────
APP_WIDTH = 'max-w-[1920px]'
DEBUG_GRID = False

# ── Shared display thresholds (case-agnostic alarm limits) ─────────────────
PID_WARNING_THRESHOLDS = {
    'level_high': 0.85,
    'level_low': 0.15,
    'temp_high': 90.0,
    'temp_low': 20.0,
    'pressure_high': 5.0,
    'pressure_low': 0.5,
}

__all__ = [
    'STATIC_DIR',
    'APP_WIDTH',
    'DEBUG_GRID',
    'PID_WARNING_THRESHOLDS',
]
