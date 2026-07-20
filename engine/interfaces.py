# engine/interfaces.py

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, Protocol


class SimulationSessionProtocol(Protocol):
    """Minimal protocol describing what the engine expects from a session.

    This is intentionally small and focused on the surface used by
    `SimulationEngine` so the engine can remain case-agnostic.
    """

    # simulation clock (logical) in internal minutes
    t: float

    # sample period in internal minutes
    Ts: float

    # optional runner object (may be None for stateless cases)
    runner: Any | None

    # mapping name->Tag-like objects for inputs, states, outputs
    input_tags: MutableMapping[str, Any]
    state_tags: MutableMapping[str, Any]
    output_tags: MutableMapping[str, Any]

    # last observed values populated by the session after step()
    last_inputs: Mapping[str, float]
    last_states: Mapping[str, float]
    last_outputs: Mapping[str, float]

    # initial state vector or x0 fallback
    X0: list[float] | None

    # human-readable current mode name
    mode: str | None

    # time unit used by this session (e.g., 'minutes', 'seconds')
    time_unit: str

    def step(self, external_inputs: Mapping[str, float] | None = None) -> None: ...
