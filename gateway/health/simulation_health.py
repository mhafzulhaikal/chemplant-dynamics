# gateway/health/simulation_health.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimulationHealth:
    """Runtime health metrics emitted by SimulationWorker every N steps."""

    steps_per_second: float = 0.0
    queue_depth: int = 0
    tick_budget_pct: float = 0.0
    effective_acceleration: float = 1.0
    is_lagging: bool = False
