# app/pages/_runtime_manager_helpers.py

"""Shared runtime-manager helpers used by both the floating dialog
(``app.components.floating_runtime_manager``) and the dedicated
``app.pages.runtime_manager_page`` renderer.

Centralising these helpers removes a meaningful chunk of duplication
that previously lived in three places:

1. :mod:`app.pages.runtime_manager_page` — the page-level card.
2. The legacy ``tests/main.py`` test app — kept verbatim, no
   dependency on this module so the test app stays standalone.
3. (Implicit) the floating dialog body — used to embed the same
   runtime fields, so it benefits from the shared helpers too.

The module is intentionally case-agnostic. It operates on a
``bridge`` object that exposes the public surface the Runtime Manager
needs (see :class:`RuntimeManagerBridgeProtocol`); the actual
:class:`gateway.core.bridge_class.Bridge` class satisfies the protocol
through duck-typing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

# Mode pill CSS modifier classes. Kept as a module-level constant so
# callers can iterate the full set when stripping stale classes from
# a NiceGUI element.
MODE_PILL_CLASSES: tuple[str, ...] = (
    'runtime-manager-status-pill-mode-auto',
    'runtime-manager-status-pill-mode-manual',
    'runtime-manager-status-pill-mode-off',
    'runtime-manager-status-pill-mode-cascade',
    'runtime-manager-status-pill-idle',
)


class RuntimeManagerBridgeProtocol(Protocol):
    """The minimum surface the Runtime Manager helpers need from a bridge.

    Defined as a :class:`Protocol` so the helpers can be used in unit
    tests with a fake object — no concrete bridge class is required.
    """

    def supported_modes(self) -> list[str]: ...

    def apply_runtime_configuration(self, *, restart_if_needed: bool) -> None: ...

    def persist_profile(self) -> None: ...

    def queue_status(self, message: str, *, mode: str | None = None) -> None: ...
    def set_time_end_from_ui(self, value: Any) -> None: ...
    def time_end_to_text(self) -> str | None: ...

    # ``state`` exposes a small set of attributes the helpers read
    # (controller_mode, real_time, Ts, acceleration, global_sim_time,
    # scenario, input_overrides, loop_modes, last_step, status).
    # Defining the full surface here would be brittle; the helpers
    # just ``getattr`` what they need from ``bridge.state``.
    @property
    def state(self) -> Any: ...


# ──────────────────────────────────────────────────────────────
# Event-extractor — shared with ``tests/main.py``
# ──────────────────────────────────────────────────────────────


def event_value(event: Any, fallback: Any = None) -> Any:
    """Pull the actual value out of a NiceGUI event object.

    NiceGUI's ``on_change`` / ``update:model-value`` handlers receive
    either a :class:`ValueChangeEventArguments` with ``.value`` set, or
    a generic event whose ``.args`` is a dict keyed by ``value`` /
    ``newValue`` / ``modelValue`` — or, for a chip multi-select, the new
    array directly. This helper normalises all three shapes to the
    underlying value.
    """
    value = getattr(event, 'value', None)
    if value is not None:
        return value

    args = getattr(event, 'args', None)
    if isinstance(args, dict):
        for key in ('value', 'newValue', 'modelValue'):
            if args.get(key) is not None:
                return args[key]
        if len(args) == 1:
            return next(iter(args.values()))
    elif args is not None:
        return args

    return fallback


# ──────────────────────────────────────────────────────────────
# Mode / scenario helpers
# ──────────────────────────────────────────────────────────────


def normalize_mode_for_ui(bridge: RuntimeManagerBridgeProtocol, mode: str) -> str:
    """Normalize ``mode`` to one of ``bridge.supported_modes()``."""
    raw_mode = str(mode or '').strip()
    supported_modes = list(bridge.supported_modes() or [])
    for supported_mode in supported_modes:
        if str(supported_mode).strip().lower() == raw_mode.lower():
            return str(supported_mode)
    return str(supported_modes[0]) if supported_modes else raw_mode


def default_loop_mode_for_scenario(
    bridge: RuntimeManagerBridgeProtocol,
    scenario_key: str,
) -> str:
    """Return the default controller/loop mode for a scenario.

    - ``startup``     -> ``Off``
    - ``operational`` -> ``Automatic``
    - ``shutdown``    -> ``Automatic``
    """
    scenario_key = str(scenario_key or '').strip().lower()
    default_modes = {
        'startup': 'Off',
        'operational': 'Automatic',
        'shutdown': 'Automatic',
    }
    return normalize_mode_for_ui(
        bridge,
        default_modes.get(scenario_key, 'Automatic'),
    )


def mode_pill_class(mode: str) -> str:
    """Return the status-pill CSS modifier for a given mode string."""
    normalized = str(mode or '').strip().lower()
    if normalized in {'cascade', 'cas'}:
        return 'runtime-manager-status-pill-mode-cascade'
    if normalized in {'auto', 'automatic'}:
        return 'runtime-manager-status-pill-mode-auto'
    if normalized in {'manual', 'man'}:
        return 'runtime-manager-status-pill-mode-manual'
    if normalized in {'off', 'stop', 'stopped'}:
        return 'runtime-manager-status-pill-mode-off'
    return 'runtime-manager-status-pill-idle'


def mode_pill_label(mode: str) -> str:
    """Map a mode string to the short label shown on the pill."""
    normalized = str(mode or '').strip().lower()
    if normalized in {'auto', 'automatic'}:
        return 'AUTO'
    if normalized in {'manual', 'man'}:
        return 'MAN'
    if normalized in {'off', 'stop', 'stopped'}:
        return 'OFF'
    if normalized in {'cascade', 'cas'}:
        return 'CAS'
    return str(mode or '—').upper()[:6]


def apply_mode_to_controller_and_loops(
    bridge: RuntimeManagerBridgeProtocol,
    case_cfg: Any,
    mode: str,
    loop_select_refs: dict[str, Any],
    loop_displays: dict[str, Any],
    controller_select: Any = None,
) -> str:
    """Apply ``mode`` to the bridge's global controller mode and every per-loop
    mode, syncing the visible loop select / pill widgets."""
    normalized_mode = normalize_mode_for_ui(bridge, mode)
    bridge.state.controller_mode = normalized_mode

    current_loop_order = list(getattr(case_cfg, 'LOOP_ORDER', []) or [])
    if current_loop_order:
        for loop_id in current_loop_order:
            bridge.state.loop_modes[loop_id] = normalized_mode
            loop_select = loop_select_refs.get(loop_id)
            if loop_select is not None:
                try:
                    loop_select.value = normalized_mode
                except Exception:
                    pass
            loop_disp = loop_displays.get(loop_id)
            if loop_disp is not None:
                try:
                    loop_disp.text = mode_pill_label(normalized_mode)
                    _swap_pill_class(loop_disp, mode_pill_class(normalized_mode))
                except Exception:
                    pass

    if controller_select is not None:
        try:
            controller_select.value = normalized_mode
        except Exception:
            pass

    return normalized_mode


def _swap_pill_class(target: Any, mode_class: str) -> None:
    """Replace every mode-pill class on ``target`` with ``mode_class``.

    Centralised so the runtime-manager and the floating dialog use the
    same class-swap logic.
    """
    try:
        target.classes(remove=' '.join(MODE_PILL_CLASSES))
        target.classes(add=mode_class)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# Misc field helpers
# ──────────────────────────────────────────────────────────────

_SHORT_UNIT_ALIASES: dict[str, str] = {
    'seconds': 's',
    'minutes': 'min',
    'hours': 'h',
    'percent': '%',
}


def short_unit_label(unit: str) -> str:
    """Return a compact unit suffix for the unit chip next to fields."""
    normalized = str(unit or '').strip()
    if not normalized:
        return ''
    return _SHORT_UNIT_ALIASES.get(normalized.lower(), normalized[:5])


def safe_text_bind(
    label: Any,
    source: Any,
    attr: str,
    *,
    backward: Callable[[Any], str],
) -> None:
    """Bind ``label.text`` to ``getattr(source, attr)`` via ``backward``.

    Thin wrapper around :func:`ui.label.bind_text_from` that swallows
    the ``AttributeError`` raised when ``source`` isn't a bindable
    NiceGUI dataclass (some engine variants still expose a plain
    object). The label just stays at its initial text in that case.
    """
    try:
        label.bind_text_from(source, attr, backward=backward)
    except Exception:
        try:
            label.set_text(backward(getattr(source, attr, None)))
        except Exception:
            pass


def record_info(bridge: RuntimeManagerBridgeProtocol, message: str) -> None:
    """Push ``message`` to the bridge's status queue, swallowing errors."""
    try:
        bridge.queue_status(
            message,
            mode=getattr(getattr(bridge, 'state', None), 'controller_mode', None),
        )
    except Exception:
        pass


__all__ = [
    'MODE_PILL_CLASSES',
    'RuntimeManagerBridgeProtocol',
    'apply_mode_to_controller_and_loops',
    'default_loop_mode_for_scenario',
    'event_value',
    'mode_pill_class',
    'mode_pill_label',
    'normalize_mode_for_ui',
    'record_info',
    'safe_text_bind',
    'short_unit_label',
]
