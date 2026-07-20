# app/hub/children/svg_vue_child.py

from collections.abc import Callable, Mapping
from typing import Any

from nicegui.element import Element

from app.hub.engine_adapter import TickMeta


class SvgVueChild(Element, component='svg_vue_child_v2.js'):
    """Vue wrapper for SVG to allow template interpolation."""

    def __init__(self, svg_content: str, classes: str = ''):
        super().__init__()
        self._props['svg_content'] = svg_content
        self._props['snapshot'] = {}
        self._props['is_running'] = False
        self.classes(classes)

        self._computed: dict[str, Callable[[Mapping[str, float]], Any]] = {}
        self._last_snapshot_dict: dict[str, Any] = {}

    def add_computed(self, key: str, callback: Callable[[Mapping[str, float]], Any]) -> None:
        """Register a local callback to compute a derived value for the SVG."""
        self._computed[key] = callback

    def initial_sync(self, hub: Any) -> None:
        """Perform an initial sync with the hub's snapshot so Vue props are
        populated before the first tick."""
        snapshot = hub.snapshot()
        status = getattr(hub.bridge.state, 'status', 'idle')
        snapshot_dict = {}
        for key, callback in self._computed.items():
            try:
                snapshot_dict[key] = callback(snapshot)
            except Exception:
                pass
        is_running = status in ('running', 'starting')
        self._last_snapshot_dict = snapshot_dict
        self.update_snapshot(snapshot_dict, is_running)

    def on_tick(
        self,
        delta_keys: frozenset[str],
        snapshot: Mapping[str, float],
        meta: TickMeta,
    ) -> None:
        """Receive the hub's tick, run local computed properties, and push to
        Vue."""
        snapshot_dict = {}

        # Run all registered local computed properties
        for key, callback in self._computed.items():
            try:
                snapshot_dict[key] = callback(snapshot)
            except Exception:
                pass

        is_running = meta.status in ('running', 'starting')

        running_changed = is_running != self._props['is_running']
        if snapshot_dict != self._last_snapshot_dict or running_changed:
            self._last_snapshot_dict = snapshot_dict
            self.update_snapshot(snapshot_dict, is_running)

    def update_snapshot(self, snapshot_dict: dict, is_running: bool):
        """Update the reactive snapshot dictionary."""
        self._props['snapshot'] = snapshot_dict
        self._props['is_running'] = is_running
        self.update()
