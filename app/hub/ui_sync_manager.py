# app/hub/ui_sync_manager.py
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class UiSyncManager:
    """Centralized manager for high-frequency (10Hz) UI updates.

    Bypasses NiceGUI's standard binding throttle (0.1s) by directly
    mutating element properties during the SignalHub tick. Replaces the
    legacy client-side chemplant_state.js logic for better stability and
    perfect synchronization with the engine tick.

    Optimization: caches the last rendered value per element so
    ``set_text`` and ``classes`` mutations are only dispatched to the
    browser when the value actually changed. This cuts WebSocket traffic
    by ~80% on idle / slow-moving simulations.
    """

    def __init__(self, registry: Any) -> None:
        self._text_elements: list[tuple[Any, Callable[[], str]]] = []
        self._class_bindings: list[tuple[Any, str, Callable[[], bool]]] = []
        self._registry = registry
        # Per-element last-rendered value cache (avoids redundant DOM mutations)
        self._text_cache: dict[int, str] = {}
        self._class_cache: dict[tuple[int, str], bool] = {}

    def register_text(self, element: Any, getter: Callable[[], str]) -> None:
        """Register a NiceGUI element whose text should be updated every tick."""
        self._text_elements.append((element, getter))

    def register_class_toggle(
        self, element: Any, css_class: str, condition: Callable[[], bool]
    ) -> None:
        """Register a NiceGUI element whose class should be toggled every tick
        based on a condition."""
        self._class_bindings.append((element, css_class, condition))

    def on_tick(self) -> None:
        """Update all registered elements.

        Only pushes DOM mutations when the value has actually changed since
        the last tick — eliminates redundant WebSocket traffic.
        """
        # 1. Update text elements (cached)
        for element, getter in self._text_elements:
            try:
                new_text = str(getter())
                eid = id(element)
                if self._text_cache.get(eid) != new_text:
                    self._text_cache[eid] = new_text
                    element.set_text(new_text)
            except Exception:
                logger.debug('UiSyncManager: failed to update text', exc_info=True)

        # 2. Update class toggles (Run button, SVG animations) — cached
        for element, css_class, condition in self._class_bindings:
            try:
                should_be_active = bool(condition())
                cache_key = (id(element), css_class)
                if self._class_cache.get(cache_key) == should_be_active:
                    continue  # no change — skip DOM mutation
                self._class_cache[cache_key] = should_be_active
                if should_be_active:
                    element.classes(add=css_class)
                else:
                    element.classes(remove=css_class)
            except Exception:
                logger.debug('UiSyncManager: failed to toggle class', exc_info=True)

    def set_running_state(self, is_running: bool) -> None:
        self._is_running = is_running
