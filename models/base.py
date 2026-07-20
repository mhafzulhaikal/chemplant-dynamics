from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class PlantSystemBase(ABC):
    """Contract for plant model wrappers exposed to builders and sessions."""

    plant_name: str = 'plant'
    default_time_unit: str = 'minutes'

    @abstractmethod
    def default_state(self) -> Sequence[float]:
        """Return a default state vector for this plant."""
