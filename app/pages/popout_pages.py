# app/pages/popout_pages.py

"""Independent pop-out pages for multi-screen monitoring."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from app.components.floating_runtime_manager import FloatingRuntimeManager
from app.hub.data_logger import (
    render_data_logger_unified,
)
from app.hub.perf_monitor import (
    render_performance_monitor_unified,
)
from app.layouts.popout_shell import popout_shell
from app.layouts.shell import setup_page_shell
from app.pages.control_panel_page import _CASE_HANDLERS, _build_pid_section
from app.pages.runtime_manager_page import render_runtime_manager_body
from app.pid.biodiesel.hub_factory import build_biodiesel_hub

# We need the hub factory for each case.
from app.pid.sthr.hub_factory import build_sthr_hub
from gateway.registry.config_registry import get_case_config


def _get_hub_for_case(case_slug: str):
    if case_slug == 'sthr':
        return build_sthr_hub()
    elif case_slug == 'biodiesel':
        return build_biodiesel_hub()
    else:
        raise ValueError(f'Unknown case: {case_slug}')


def register_popout_routes(case_slug: str) -> None:
    """Register the three pop-out routes for a given simulation case."""

    @ui.page(f'/popout/{case_slug}/pid')
    def pid_popout_base() -> None:
        import uuid

        popout_id = uuid.uuid4().hex[:6]
        ui.navigate.to(f'/popout/{case_slug}/pid/{popout_id}')

    @ui.page(f'/popout/{case_slug}/pid/{{popout_id}}')
    def pid_popout_page(popout_id: str) -> None:  # noqa: ARG001
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return
        handlers = _CASE_HANDLERS[case_slug]

        @dataclass
        class _RuntimeManagerShim:
            bridge: Any
            reset: Callable[[], None]

        def _standalone_reset() -> None:
            hub.engine_control.reset()
            hub.reset_snapshot_to_seed()

        def _on_run() -> None:
            try:
                hub.engine_control.run()
                ui.notify(
                    'Simulation Running',
                    type='positive',
                    position='bottom-right',
                )
            except Exception as e:
                ui.notify(
                    f'Run failed: {e}',
                    type='negative',
                    position='bottom-right',
                )

        def _on_stop() -> None:
            try:
                hub.engine_control.stop()
                ui.notify('Simulation Stopped', type='info', position='bottom-right')
            except Exception as e:
                ui.notify(
                    f'Stop failed: {e}',
                    type='negative',
                    position='bottom-right',
                )

        def _content():
            shim = _RuntimeManagerShim(bridge=hub.bridge, reset=_standalone_reset)
            floating_runtime_manager = FloatingRuntimeManager(
                case_slug=case_slug,
                process_label=handlers.process_label,
                build_store=lambda s=shim: s,
                on_run=_on_run,
                on_stop=_on_stop,
            )
            _build_pid_section(
                handlers,
                hub,
                case_slug,
                on_runtime_manager_click=floating_runtime_manager.toggle,
                popout_url=None,
            )

        popout_shell('Piping & Instrumentation Diagram', _content)

        hub.start()
        ui.timer(hub.tick_s, hub.tick_once)

    @ui.page(f'/popout/{case_slug}/perf-monitor')
    def perf_monitor_popout_base() -> None:
        import uuid

        popout_id = uuid.uuid4().hex[:6]
        ui.navigate.to(f'/popout/{case_slug}/perf-monitor/{popout_id}')

    @ui.page(f'/popout/{case_slug}/perf-monitor/{{popout_id}}')
    def perf_monitor_popout_page(popout_id: str) -> None:
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return

        def _content():
            render_performance_monitor_unified(
                hub,
                case_slug=case_slug,
                is_popout=True,
                show_header=True,
                popout_id=popout_id,
            )

        popout_shell(
            'Performance Monitoring',
            _content,
        )

        hub.start()
        ui.timer(hub.tick_s, hub.tick_once)

    @ui.page(f'/popout/{case_slug}/data-logger')
    def data_logger_popout_base() -> None:
        import uuid

        popout_id = uuid.uuid4().hex[:6]
        ui.navigate.to(f'/popout/{case_slug}/data-logger/{popout_id}')

    @ui.page(f'/popout/{case_slug}/data-logger/{{popout_id}}')
    def data_logger_popout_page(popout_id: str) -> None:
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return

        def _content():
            render_data_logger_unified(
                hub,
                case_slug=case_slug,
                is_popout=True,
                show_header=True,
                popout_id=popout_id,
            )

        popout_shell('Data Logger', _content)

        hub.start()
        ui.timer(hub.tick_s, hub.tick_once)

    @ui.page(f'/runtime-manager/{case_slug}')
    def runtime_manager_standalone_page() -> None:
        setup_page_shell(body_class='control-panel-page')
        hub = _get_hub_for_case(case_slug)
        if hub is None:
            ui.label('Engine not available.').classes('text-white/70 p-4')
            return
        case_cfg = get_case_config(case_slug)
        handlers = _CASE_HANDLERS[case_slug]

        @dataclass
        class _RuntimeManagerShim:
            bridge: Any
            reset: Callable[[], None]

        def _standalone_reset() -> None:
            hub.engine_control.reset()
            hub.reset_snapshot_to_seed()

        def _on_run() -> None:
            try:
                hub.engine_control.run()
                ui.notify(
                    'Simulation Running',
                    type='positive',
                    position='bottom-right',
                )
            except Exception as e:
                ui.notify(
                    f'Run failed: {e}',
                    type='negative',
                    position='bottom-right',
                )

        def _on_stop() -> None:
            try:
                hub.engine_control.stop()
                ui.notify('Simulation Stopped', type='info', position='bottom-right')
            except Exception as e:
                ui.notify(
                    f'Stop failed: {e}',
                    type='negative',
                    position='bottom-right',
                )

        shim = _RuntimeManagerShim(bridge=hub.bridge, reset=_standalone_reset)

        with ui.column().classes('w-full min-h-screen items-center justify-center bg-black/90 p-4'):
            # The standalone page gets no close/minimize buttons
            render_runtime_manager_body(
                case_cfg=case_cfg,
                bridge=hub.bridge,
                store=shim,
                process_label=handlers.process_label,
                on_run=_on_run,
                on_stop=_on_stop,
            )

        hub.start()
        ui.timer(hub.tick_s, hub.tick_once)


# Pre-register for both known cases
register_popout_routes('sthr')
register_popout_routes('biodiesel')
