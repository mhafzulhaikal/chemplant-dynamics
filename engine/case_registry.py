# engine/case_registry.py

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import TYPE_CHECKING

# Registry maps case name -> factory_creator(appdb) -> session_factory()
if TYPE_CHECKING:
    from engine.interfaces import SimulationSessionProtocol

_registry: dict[str, Callable[[object], Callable[[], SimulationSessionProtocol]]] = {}


def register_case(
    name: str, factory_creator: Callable[[object], Callable[[], SimulationSessionProtocol]]
) -> None:
    """Register a case plugin programmatically.

    `factory_creator` is a callable that accepts `appdb` and returns a
    zero-argument `session_factory` which when called returns a session
    instance.
    """
    _registry[name] = factory_creator


def discover_cases() -> dict[str, Callable[[object], Callable[[], SimulationSessionProtocol]]]:
    """Discover case plugins under the `cases` package.

    Looks for `cases.<name>.session` modules. The module may export either:
      - `create_session(appdb)` factory function, or
      - a Session class named `STHRSimulationSession` (or similar), which
        will be constructed with `cls(appdb=appdb)`.
    """
    found: dict[str, Callable[[object], Callable[[], SimulationSessionProtocol]]] = dict(_registry)
    try:
        import cases
    except Exception:
        return found

    for _finder, modname, _ispkg in pkgutil.iter_modules(cases.__path__):
        try:
            mod = importlib.import_module(f'cases.{modname}.session')
        except Exception:
            continue

        # prefer an explicit factory
        if hasattr(mod, 'create_session'):
            # create_session(appdb) should itself return a zero-arg factory;
            # return that factory directly (no extra wrapping).
            found[modname] = lambda appdb, m=mod: m.create_session(appdb)
            continue

        # else try to find a plausible session class
        for cls_name in ('SimulationSession', 'STHRSimulationSession'):
            cls = getattr(mod, cls_name, None)
            if cls is not None:
                found[modname] = lambda appdb, cls=cls: lambda: cls(appdb=appdb)
                break

    return found


def list_cases() -> list[str]:
    return sorted(discover_cases().keys())


def get_session_factory(case_name: str, appdb: object) -> Callable[[], SimulationSessionProtocol]:
    cases = discover_cases()
    if case_name not in cases:
        raise KeyError(f"Unknown case '{case_name}'. Available: {sorted(cases.keys())}")
    return cases[case_name](appdb)
