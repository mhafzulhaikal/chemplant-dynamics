from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CaseRuntimeConfig:
    case_name: str
    supported_modes: tuple[str, ...]
    default_mode: str
    time_unit: str


def normalize_mode(mode: str | None, default_mode: str) -> str:
    return str(mode or default_mode).strip().lower()


def merge_input_dicts(
    base: Mapping[str, float],
    overrides: Mapping[str, float] | None,
) -> dict[str, float]:
    merged = {k: float(v) for k, v in base.items()}
    if overrides:
        for key, value in overrides.items():
            merged[str(key)] = float(value)
    return merged


InputProvider = Callable[[str], Mapping[str, float]]
