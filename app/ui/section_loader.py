# app/ui/section_loader.py

"""Deferred section mount pattern.

When the user clicks a left-drawer item, the section builder can
block the UI thread for 200-600 ms (echarts, SVG, tables).  The
two-stage mount fixes this:

* **Stage 1 — immediate.** A spinner overlay is painted and the
  click handler returns instantly.

* **Stage 2 — deferred.** An ``asyncio`` task sleeps for 0 s then
  runs the real builder, so the click response has already flushed.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.ui.loading import (
    render_spinner_overlay,
    replace_with_real,
)

logger = logging.getLogger(__name__)


DEFAULT_HEIGHTS: dict[str, int] = {
    'overview': 240,
    'Piping and Instrumentation Diagram': 540,
    'Performance Monitoring': 520,
    'Data Logger': 480,
}


def _guess_height(label: str) -> int:
    if not label:
        return 320
    if 'Piping' in label or 'P&ID' in label or 'Instrumentation' in label:
        return DEFAULT_HEIGHTS['Piping and Instrumentation Diagram']
    if 'Monitoring' in label or 'Performance' in label:
        return DEFAULT_HEIGHTS['Performance Monitoring']
    if 'Logger' in label or 'Data' in label:
        return DEFAULT_HEIGHTS['Data Logger']
    if 'Overview' in label:
        return DEFAULT_HEIGHTS['overview']
    return 320


def _classify_section(label: str) -> str:
    if 'Piping' in label or 'P&ID' in label or 'Instrumentation' in label:
        return 'pid'
    if 'Monitoring' in label or 'Performance' in label:
        return 'monitoring'
    if 'Logger' in label or 'Data' in label:
        return 'logger'
    return 'overview'


def _build_section_skeleton(label: str) -> Any:
    return render_spinner_overlay(_label=f'Loading {label}...')


class SectionLoader:
    """Two-stage section mount helper.

    Usage::

        loader = SectionLoader(panel, label='P&ID', builder=build_pid)
        loader.mount()   # idempotent
    """

    def __init__(
        self,
        panel: Any,
        *,
        label: str,
        builder: Callable[[], None],
    ) -> None:
        self._panel = panel
        self._label = str(label)
        self._builder = builder
        self._mounted: bool = False
        self._skeleton: Any | None = None
        # Guard against double-mount when a click fires while a
        # previous timer is still pending.
        self._mount_in_progress: bool = False

    @property
    def is_mounted(self) -> bool:
        return self._mounted

    @property
    def label(self) -> str:
        return self._label

    def mount(self) -> None:
        """Show the panel, mount the skeleton, schedule the builder."""
        if self._mounted or self._mount_in_progress:
            return
        self._mount_in_progress = True

        try:
            with self._panel:
                self._skeleton = _build_section_skeleton(self._label)
        except Exception:
            logger.exception(
                'SectionLoader: failed to mount skeleton for %s',
                self._label,
            )
            self._mount_in_progress = False
            self._run_builder()
            return

        # Use ``asyncio`` instead of ``ui.timer`` so no NiceGUI element
        # (with a parent slot) is created.  When the user switches
        # sections rapidly the panel may be cleared before the timer
        # fires; a plain ``ui.timer`` created inside that panel would
        # raise ``RuntimeError: The parent slot of the element has
        # been deleted.`` because its slot was removed with the panel.
        async def _deferred() -> None:
            await asyncio.sleep(0)
            try:
                self._run_builder()
            except Exception:
                logger.exception(
                    'SectionLoader: deferred builder for %s raised',
                    self._label,
                )

        try:
            asyncio.create_task(_deferred())
        except Exception:
            self._run_builder()

    def _run_builder(self) -> None:
        if self._mounted:
            self._mount_in_progress = False
            return
        try:
            with self._panel:
                self._builder()
        except Exception:
            logger.exception(
                'SectionLoader: builder for %s raised',
                self._label,
            )
        self._mounted = True
        self._mount_in_progress = False
        if self._skeleton is not None:
            try:
                replace_with_real(self._skeleton)
            except Exception:
                pass
            self._skeleton = None


__all__ = ['SectionLoader', 'DEFAULT_HEIGHTS']
