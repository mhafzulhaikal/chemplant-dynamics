# gateway/core/bridge_support.py

"""Case-agnostic supporting types for :mod:`gateway.core.bridge_class`.

Originally part of ``gateway/core/bridge_class_support.py`` — the contents
have always been case-agnostic (the dataclass holds generic engine /
UI state, the helper converts any value to a safe float). The
``sthr_`` prefix was a historical relic; the new module exports:

- :class:`BridgeState` — the bindable dataclass the engine bridge
  uses for live UI state.
- :class:`BridgeRecord` — the queue payload pushed from the worker
  to the NiceGUI side every simulation step.
- :func:`safe_float` — defensive float coercion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from nicegui import binding


def safe_float(
    value: Any,
    default: float,
    *,
    minimum: float | None = None,
    allow_inf: bool = False,
) -> float:
    """
    Convert value ke float secara aman.

    Mendukung:
        - None
        - string kosong
        - value invalid
        - NaN
        - Inf / infinity / ∞ jika allow_inf=True
        - minimum hanya diterapkan untuk nilai finite
    """

    try:
        if value is None:
            result = float(default)

        elif isinstance(value, str):
            text = value.strip().lower()

            if not text:
                result = float(default)

            elif allow_inf and text in {
                'inf',
                '+inf',
                'infinity',
                '+infinity',
                '∞',
                'none',
                'null',
                'no end',
                'no_end',
                'unlimited',
            }:
                result = float('inf')

            else:
                result = float(value)

        else:
            result = float(value)

    except (TypeError, ValueError):
        result = float(default)

    if math.isnan(result):
        result = float(default)

    if minimum is not None and math.isfinite(result):
        result = max(result, float(minimum))

    return result


@binding.bindable_dataclass
class BridgeState:
    controller_mode: str = ''

    Ts: float = 0.01

    # Definisi:
    #   real_time=True:
    #       simulasi real-time, acceleration diabaikan.
    #
    #   real_time=False:
    #       simulasi mengikuti acceleration.
    #
    #   acceleration=1:
    #       setara real-time.
    #
    #   acceleration>1:
    #       lebih cepat.
    #
    #   acceleration<1:
    #       lebih lambat.
    acceleration: float = 1.0

    real_time: bool = True

    # float('inf') berarti tanpa batas akhir simulasi.
    # angka finite berarti waktu akhir absolute sesuai session.time_unit.
    time_end: float = float('inf')

    running: bool = False
    status: str = 'idle'

    last_step: int = -1
    last_sim_time: float = 0.0
    global_sim_time: float = 0.0

    # True when the previous worker exited by reaching time_end (a "natural"
    # finish) rather than via reset()/stop(). The Data Logger and Performance
    # Plot use this flag to decide whether a worker restart should append to
    # the existing chart/log history or wipe it.
    natural_stop: bool = False

    selected_log_fields: list[str] = field(default_factory=list)
    available_log_fields: list[str] = field(default_factory=list)
    input_overrides: dict[str, float] = field(default_factory=dict)
    loop_modes: dict[str, str] = field(default_factory=dict)
    scenario: str = 'operational'
    health: object = None


@dataclass(slots=True)
class BridgeRecord:
    kind: str
    message: str

    step_index: int | None = None
    time_min: float | None = None
    real_time: str | None = None
    mode: str | None = None

    inputs: dict[str, float] = field(default_factory=dict)
    states: dict[str, float] = field(default_factory=dict)
    outputs: dict[str, float] = field(default_factory=dict)

    selected_fields: list[str] = field(default_factory=list)
