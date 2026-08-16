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

    def __init__(
        self,
        controller_mode: str,
        Ts: float,
        acceleration: float,
        real_time: bool,
        time_end: float,
        loop_modes: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, 'controller_mode', str(controller_mode))
        object.__setattr__(self, 'Ts', float(Ts))
        object.__setattr__(self, 'acceleration', float(acceleration))
        object.__setattr__(self, 'real_time', bool(real_time))
        object.__setattr__(self, 'time_end', float(time_end))
        object.__setattr__(
            self,
            'loop_modes',
            dict(loop_modes) if loop_modes is not None else {},
        )
