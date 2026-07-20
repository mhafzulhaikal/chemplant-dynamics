from __future__ import annotations

import importlib
import pkgutil
from typing import Any


def discover_case_configs() -> dict[str, Any]:
    """Discover config modules under cases.<name>.config."""
    found: dict[str, Any] = {}
    try:
        import cases
    except Exception:
        return found

    for _, modname, _ in pkgutil.iter_modules(cases.__path__):
        try:
            cfg_mod = importlib.import_module(f'cases.{modname}.config')
        except Exception:
            continue
        found[modname] = cfg_mod

    return found


def get_case_config(case_name: str):
    configs = discover_case_configs()
    if case_name not in configs:
        raise KeyError(f"Unknown case config '{case_name}'. Available: {sorted(configs.keys())}")
    return configs[case_name]


def list_case_configs() -> list[str]:
    return sorted(discover_case_configs().keys())
