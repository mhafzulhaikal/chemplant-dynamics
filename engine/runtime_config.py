# engine/runtime_config.py

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    controller_mode: str
    Ts: float
    acceleration: float
    real_time: bool
    time_end: float
    loop_modes: dict[str, str] = field(default_factory=dict)
