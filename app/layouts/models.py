# app/layouts/models.py

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlPanelSection:
    label: str
    builder: Callable[[], None]


@dataclass(frozen=True)
class ControlPanelConfig:
    sections: tuple[ControlPanelSection, ...]
    default_section: str
