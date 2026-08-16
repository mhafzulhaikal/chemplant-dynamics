# app/pages/popout_pages.py

"""Independent pop-out pages for multi-screen monitoring.

Architecture
------------
Every popout page obtains its hub via ``_get_hub_for_case()``, which
delegates to the same per-case factory used by the main control-panel
page (``_CASE_HANDLERS`` in ``control_panel_page``).

Because the factory keys the hub registry on ``browser_id``, a popout
opened in the **same browser** automatically shares the live bridge
(running engine, recorded history, selected fields) with the main tab.
A popout opened in a **different browser** gets a fresh bridge -- this
is intentional: each browser session owns its own simulation state.

Hub startup
-----------
- ``pid_popout_page``: ``hub.start()`` is called inside
  ``_build_pid_section()`` (from ``control_panel_page``), so no
  explicit call is needed here.
- ``perf_monitor_popout_page`` / ``data_logger_popout_page``: their
  content renderers do NOT call ``hub.start()`` internally, so an
  explicit ``hub.start()`` is required at the end of each handler.
- ``runtime_manager_standalone_page``: same -- explicit call at end.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from app.components.floating_runtime_manager import FloatingRuntimeManager
from app.hub.data_logger import render_data_logger_unified
from app.hub.perf_monitor import render_performance_monitor_unified
from app.layouts.popout_shell import popout_shell
from app.layouts.shell import setup_page_shell
from app.pages.control_panel_page import _CASE_HANDLERS, _build_pid_section
from app.pages.runtime_manager_page import render_runtime_manager_body
from gateway.registry.config_registry import get_case_config

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@dataclass
class _RuntimeManagerShim:
    """Minimal adapter so ``FloatingRuntimeManager`` and
    ``render_runtime_manager_body`` can drive the engine via the hub.

    Exposes ``.bridge`` (for the runtime manager body) and ``.reset()``
    (for the scenario-change reset hook in ``runtime_manager_page``).
    Previously this was duplicated as an inner class in each page handler.
    """

    bridge: Any
    hub: Any
    reset: Any  # Callable[[], None]


def _get_hub_for_case(case_slug: str) -> Any:
    """Return (or build) the per-browser hub for *case_slug*.

    Delegates to the same factory used by the main control-panel so that
    a popout opened in the same browser shares the running bridge.
    Adding a new case only requires updating ``_CASE_HANDLERS``.
    """
    handlers = _CASE_HANDLERS.get(case_slug)
    if handlers is None:
        raise ValueError(f'Unknown case slug: {case_slug!r}')
    return handlers.build_hub()


def _make_engine_handlers(hub: Any, case_slug: str) -> tuple:
    """Return ``(on_run, on_stop, on_reset)`` closures for a popout page.

    Each handler:
    - calls the engine method via ``hub.engine_control``,
    - shows a ``ui.notify`` feedback toast, and
    - writes an audit log entry.

    ``on_reset`` also calls ``hub.reset_snapshot_to_seed()`` so the
    hub's in-memory snapshot returns to initial conditions -- matching
    the main control-panel's Reset handler behaviour.
    """
    bridge = hub.engine_control.bridge if hub is not None else None

    def _on_run() -> None:
        if hub is None:
            return
        try:
            hub.engine_control.run()
            ui.notify(
                'Simulation Running',
                color='blue-grey-8',
                icon='check_circle_outline',
                position='bottom-right',
            )
        except Exception as exc:
            ui.notify(
                f'Run failed: {exc}',
                type='negative',
                position='bottom-right',
            )
            return
        try:
            from app.hub.data_logger import write_audit_log

            write_audit_log(
                case_slug,
                f'Simulation Started (via {case_slug.upper()} Popout)',
                bridge=bridge,
            )
        except Exception:
            pass

    def _on_stop() -> None:
        if hub is None:
            return
        try:
            hub.engine_control.stop()
            ui.notify(
                'Simulation Stopped',
                color='blue-grey-8',
                icon='stop',
                position='bottom-right',
            )
        except Exception as exc:
            ui.notify(
                f'Stop failed: {exc}',
                type='negative',
                position='bottom-right',
            )
            return
        try:
            from app.hub.data_logger import write_audit_log

            write_audit_log(
                case_slug,
                f'Simulation Paused (via {case_slug.upper()} Popout)',
                bridge=bridge,
            )
        except Exception:
            pass

    def _on_reset() -> None:
        if hub is None:
            return
        try:
            hub.engine_control.reset()
            hub.reset_snapshot_to_seed()
            ui.notify(
                'Simulation Reset',
                color='blue-grey-8',
                icon='restart_alt',
                position='bottom-right',
            )
        except Exception as exc:
            ui.notify(
                f'Reset failed: {exc}',
                type='negative',
                position='bottom-right',
            )
            return
        try:
            from app.hub.data_logger import write_audit_log

            write_audit_log(
                case_slug,
                f'Simulation Reset (via {case_slug.upper()} Popout)',
                bridge=bridge,
            )
        except Exception:
            pass

    return _on_run, _on_stop, _on_reset


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_popout_routes(case_slug: str) -> None:
    """Register the pop-out routes for a given simulation case.

    Routes:
    - ``/popout/{slug}/pid[/{id}]``           -- P&ID diagram
    - ``/popout/{slug}/perf-monitor[/{id}]``  -- Performance Monitor
    - ``/popout/{slug}/data-logger[/{id}]``   -- Data Logger
    - ``/runtime-manager/{slug}``             -- standalone Runtime Manager
    """

    # -- PID popout --------------------------------------------------------

    @ui.page(f'/popout/{case_slug}/pid')
    def pid_popout_base() -> None:
        ui.navigate.to(f'/popout/{case_slug}/pid/{_uuid.uuid4().hex[:6]}')

    @ui.page(f'/popout/{case_slug}/pid/{{popout_id}}')
    def pid_popout_page(popout_id: str) -> None:  # noqa: ARG001
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return

        handlers = _CASE_HANDLERS[case_slug]
        on_run, on_stop, on_reset = _make_engine_handlers(hub, case_slug)

        shim = _RuntimeManagerShim(bridge=hub.bridge, hub=hub, reset=on_reset)

        def _content() -> None:
            frm = FloatingRuntimeManager(
                case_slug=case_slug,
                process_label=handlers.process_label,
                build_store=lambda s=shim: s,
                on_run=on_run,
                on_stop=on_stop,
            )
            _build_pid_section(
                handlers,
                hub,
                case_slug,
                on_runtime_manager_click=frm.toggle,
                popout_url=None,
            )
            # hub.start() is called inside _build_pid_section() -- no
            # explicit call needed here.

        popout_shell('Piping & Instrumentation Diagram', _content)

    # -- Performance Monitor popout ----------------------------------------

    @ui.page(f'/popout/{case_slug}/perf-monitor')
    def perf_monitor_popout_base() -> None:
        ui.navigate.to(f'/popout/{case_slug}/perf-monitor/{_uuid.uuid4().hex[:6]}')

    @ui.page(f'/popout/{case_slug}/perf-monitor/{{popout_id}}')
    def perf_monitor_popout_page(popout_id: str) -> None:
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return

        def _content() -> None:
            render_performance_monitor_unified(
                hub,
                case_slug=case_slug,
                is_popout=True,
                show_header=True,
                popout_id=popout_id,
            )

        popout_shell('Performance Monitoring', _content)
        # render_performance_monitor_unified does NOT call hub.start()
        # -- this is the sole startup call for this popout.
        hub.start()

    # -- Data Logger popout ------------------------------------------------

    @ui.page(f'/popout/{case_slug}/data-logger')
    def data_logger_popout_base() -> None:
        ui.navigate.to(f'/popout/{case_slug}/data-logger/{_uuid.uuid4().hex[:6]}')

    @ui.page(f'/popout/{case_slug}/data-logger/{{popout_id}}')
    def data_logger_popout_page(popout_id: str) -> None:
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return

        def _content() -> None:
            render_data_logger_unified(
                hub,
                case_slug=case_slug,
                is_popout=True,
                show_header=True,
                popout_id=popout_id,
            )

        popout_shell('Data Logger', _content)
        # render_data_logger_unified does NOT call hub.start()
        # -- this is the sole startup call for this popout.
        hub.start()

    # -- Standalone Runtime Manager ----------------------------------------

    @ui.page(f'/runtime-manager/{case_slug}')
    def runtime_manager_standalone_page() -> None:
        setup_page_shell(body_class='control-panel-page')
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return

        case_cfg = get_case_config(case_slug)
        handlers = _CASE_HANDLERS[case_slug]
        on_run, on_stop, on_reset = _make_engine_handlers(hub, case_slug)

        shim = _RuntimeManagerShim(bridge=hub.bridge, hub=hub, reset=on_reset)

        with ui.column().classes('w-full min-h-screen items-center justify-center bg-black/90 p-4'):
            # The standalone page has no close/minimize buttons.
            render_runtime_manager_body(
                case_cfg=case_cfg,
                bridge=hub.bridge,
                store=shim,
                process_label=handlers.process_label,
                on_run=on_run,
                on_stop=on_stop,
            )

        # render_runtime_manager_body does NOT call hub.start()
        # -- this is the sole startup call for this page.
        hub.start()


# Pre-register for both known cases at import time.
register_popout_routes('sthr')
register_popout_routes('biodiesel')
