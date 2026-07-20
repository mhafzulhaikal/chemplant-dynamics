# app/pid/biodiesel/hub_factory.py

"""Biodiesel :class:`SignalHub` factory.

Owns the per-browser bridge registry for biodiesel. Same pattern as
:mod:`app.pid.sthr.hub_factory` — one bridge per browser session, reused
across page reloads; a single shutdown hook installed at module import.
"""

from __future__ import annotations

import logging
from typing import Any

from nicegui import app

from app.hub.signal_hub import SignalHub
from app.pid.biodiesel.registry import BIODIESEL_REGISTRY

logger = logging.getLogger(__name__)


# ── Engine connection (lazy import) ──
_ENGINE_AVAILABLE = False
_GenericBridge: Any = None
_get_case_config: Any = None

try:
    from gateway.bridge import Bridge as _GenericBridge
    from gateway.registry.config_registry import get_case_config as _get_case_config

    _ENGINE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    logger.warning(
        'Biodiesel engine gateway not importable — page will not start: %s',
        exc,
    )


# ── Config-derived seed ──
# Import the case config directly so seed values stay in sync with the
# authoritative initial conditions.  The lazy-import guard above means
# this import is only attempted when the engine is available.
_ACTUATOR_STATE: Any = None
_PLANT_INPUT: Any = None
_PLANT_STATE: Any = None
_REFERENCE_INPUT: Any = None
initial_states_for_scenario: Any = None
try:
    from cases.biodiesel.config import (
        ACTUATOR_STATE as _ACTUATOR_STATE,
    )
    from cases.biodiesel.config import (
        PLANT_INPUT as _PLANT_INPUT,
    )
    from cases.biodiesel.config import (
        PLANT_STATE as _PLANT_STATE,
    )
    from cases.biodiesel.config import (
        REFERENCE_INPUT as _REFERENCE_INPUT,
    )
    from cases.biodiesel.config import (
        initial_states_for_scenario,
    )

    _HAVE_CONFIG = True
except Exception:
    _HAVE_CONFIG = False


# Per-browser bridge registry. Independent of the STHR registry —
# each case has its own dict and its own shutdown hook so cross-case
# isolation is preserved.
_BIODIESEL_BRIDGE_REGISTRY: dict[str, Any] = {}
_BIODIESEL_HUB_REGISTRY: dict[str, SignalHub] = {}


def _shutdown_bridges() -> None:
    """Stop every biodiesel bridge on application shutdown."""
    for hub in _BIODIESEL_HUB_REGISTRY.values():
        try:
            hub.stop()
        except Exception:
            pass
    for bridge in _BIODIESEL_BRIDGE_REGISTRY.values():
        try:
            bridge.stop()
        except Exception:
            logger.exception('Failed to stop biodiesel bridge on shutdown')


if _ENGINE_AVAILABLE:
    app.on_shutdown(_shutdown_bridges)


def _get_bridge(profile_key: str) -> Any:
    """Return an existing biodiesel bridge for the profile, or create one."""
    bridge = _BIODIESEL_BRIDGE_REGISTRY.get(profile_key)
    if bridge is None:
        bridge = _GenericBridge(case_name='biodiesel')
        _BIODIESEL_BRIDGE_REGISTRY[profile_key] = bridge
    return bridge


def _initial_pv_seed(scenario: str = 'operational') -> dict[str, float]:
    """Seed the hub snapshot with the same display values the SVG was baked
    with.

    The SVG is rendered by
    :func:`app.biodiesel_drawing.build_biodiesel_drawing`
    using hard-coded initial values. Without this seed, the hub's
    snapshot is empty until the first engine step record arrives.

    Values are sourced from ``cases/biodiesel/config.py`` so that a
    single edit to the config propagates to both the engine and the UI
    seed automatically.
    """
    if _HAVE_CONFIG:
        states = initial_states_for_scenario(scenario)
        return {
            'tic_pv': states.get('biodiesel_reactor.T', _PLANT_STATE['T']),
            'tic_sp': _REFERENCE_INPUT['TSP-100.SP'],
            'lic_pv': states.get('biodiesel_reactor.h', _PLANT_STATE['h']),
            'lic_sp': _REFERENCE_INPUT['LSP-100.SP'],
            'fic100_pv': _PLANT_INPUT['biodiesel_reactor.f_oil'],
            'fic101_pv': _PLANT_INPUT['biodiesel_reactor.f_MeOH'],
            'fic102_pv': _PLANT_INPUT['biodiesel_reactor.f_NaOH'],
            'ti100_pv': _PLANT_INPUT['biodiesel_reactor.T_oil'],
            'ti100_sp': _PLANT_INPUT['biodiesel_reactor.T_oil'],
            'ti101_pv': _PLANT_INPUT['biodiesel_reactor.T_MeOH'],
            'ti101_sp': _PLANT_INPUT['biodiesel_reactor.T_MeOH'],
            'ti102_pv': _PLANT_INPUT['biodiesel_reactor.T_NaOH'],
            'ti102_sp': _PLANT_INPUT['biodiesel_reactor.T_NaOH'],
            'ti103_pv': _PLANT_INPUT['biodiesel_reactor.T_coolant_in'],
            'ti103_sp': _PLANT_INPUT['biodiesel_reactor.T_coolant_in'],
            'ti104_pv': states.get('biodiesel_reactor.T_coolant', _PLANT_STATE['T_coolant']),
            'fi100_pv': _PLANT_INPUT['biodiesel_reactor.f_coolant'],
            'fi101_pv': _PLANT_INPUT['biodiesel_reactor.f_FAME'],
            'pi100_pv': 4.0,
            'lic_vp': _ACTUATOR_STATE['LV-100.vp'],
            'tic_vp': _ACTUATOR_STATE['TV-100.vp'],
            'fic100_vp': _ACTUATOR_STATE['FV-100.vp'],
            'fic101_vp': _ACTUATOR_STATE['FV-101.vp'],
            'fic102_vp': _ACTUATOR_STATE['FV-102.vp'],
        }

    # Fallback — used when the config module is not importable
    # (e.g. during tests or in environments without the engine).
    return {
        'tic_pv': 333.15,
        'tic_sp': 333.15,
        'lic_pv': 1.50,
        'lic_sp': 1.50,
        'fic100_pv': 3.29675e-04,
        'fic101_pv': 8.33750e-05,
        'fic102_pv': 1.33405e-05,
        'ti100_pv': 333.15,
        'ti100_sp': 333.15,
        'ti101_pv': 298.15,
        'ti101_sp': 298.15,
        'ti102_pv': 298.15,
        'ti102_sp': 298.15,
        'ti103_pv': 298.15,
        'ti103_sp': 298.15,
        'ti104_pv': 323.15,
        'fi100_pv': 1.5114e-04,
        'fi101_pv': 4.6882e-04,
        'pi100_pv': 4.0,
        'lic_vp': 50.0,
        'tic_vp': 20.0,
        'fic100_vp': 50.0,
        'fic101_vp': 50.0,
        'fic102_vp': 50.0,
    }


def build_biodiesel_hub(
    *,
    initial: dict[str, float] | None = None,
) -> SignalHub | None:
    """Build (or reuse) the per-browser bridge and wrap it in a SignalHub.

    Returns ``None`` when the engine gateway is unavailable — the page
    handles that by showing an "engine not connected" placeholder.
    """
    if not _ENGINE_AVAILABLE:
        return None

    try:
        case_cfg = _get_case_config('biodiesel')
        case_runtime = getattr(case_cfg, 'CASE_RUNTIME', None)
        case_default_mode = str(
            getattr(case_runtime, 'default_mode', 'automatic'),
        )
        case_default_mode_display = (
            case_default_mode
            if any(ch.isupper() for ch in case_default_mode)
            else case_default_mode.capitalize()
        )

        browser_id = str(app.storage.browser.get('id', 'default-browser'))
        profile_key = f'{_GenericBridge.profile_storage_prefix}:biodiesel:{browser_id}'

        hub = _BIODIESEL_HUB_REGISTRY.get(profile_key)
        if hub is not None:
            return hub

        profile = app.storage.user.setdefault(profile_key, {})

        bridge = _get_bridge(profile_key)
        bridge.bind_profile(browser_id, profile)

        if not str(bridge.state.controller_mode or '').strip():
            bridge.state.controller_mode = case_default_mode_display

        # Apply the initial runtime config so the first Run click works
        # immediately.
        bridge.apply_runtime_configuration(restart_if_needed=False)

        scenario = str(bridge.state.scenario or 'operational')
        seed = _initial_pv_seed(scenario)

        # Inject the engine's default overrides into the seed so that
        # when the user clicks 'Reset', the UI's ReactiveActionStore
        # has the complete initial configuration for all writable fields
        # (OP, Kc, Tau_i, Tau_d, etc.) instead of blanking them out.
        for spec in BIODIESEL_REGISTRY:
            if spec.writable and spec.engine_tag:
                val = bridge.state.input_overrides.get(spec.engine_tag)
                if val is not None:
                    seed[spec.modal_key] = float(val)

        if initial:
            seed.update(initial)

        hub = SignalHub(bridge, BIODIESEL_REGISTRY, initial=seed, tick_s=0.1)
        _BIODIESEL_HUB_REGISTRY[profile_key] = hub
        return hub
    except Exception:
        logger.exception('build_biodiesel_hub failed')
        return None


__all__ = ['build_biodiesel_hub', '_ENGINE_AVAILABLE']
