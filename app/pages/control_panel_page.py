# app/pages/control_panel_page.py

"""Control-panel router — hub stack (only stack after v1 purge).

Architecture:

- :func:`build_<case>_hub` (in ``app/pid/<case>/hub_factory.py``)
  builds the per-browser :class:`SignalHub` wrapping the per-browser
  :class:`Bridge`.
- The page renders the P&ID SVG, faceplate, data logger, and
  performance chart — the SVG / faceplate / modal layers attach as
  :class:`SignalHub` subscribers; the data logger and performance
  monitor consume ``hub.bridge`` directly via their own timers (port
  of the legacy renderers).
- Engine-level buttons (Run / Stop / Reset / Real Time) call
  ``hub.engine_control.<method>()`` directly — one line each.
- The Runtime Manager floating dialog is wired via a small shim that
  exposes ``.bridge`` + ``.reset()`` over the hub.

Routes registered:

- ``/control-panel``           → redirects to first case
- ``/control-panel/sthr``      → STHR control panel (hub-backed)
- ``/control-panel/biodiesel`` → biodiesel control panel (hub-backed)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from app.components.faceplate_dialog import (
    FaceplateDialog,
    FaceplateDialogConfig,
)
from app.components.floating_runtime_manager import FloatingRuntimeManager
from app.components.pid_navbar import PidNavbarConfig, render_pid_navbar
from app.hub.children import (
    FaceplateChild,
    ModalChild,
)
from app.hub.data_logger import (
    data_logger_unavailable,
    render_data_logger_section,
)
from app.hub.perf_monitor import (
    render_performance_monitor,
)
from app.hub.signal_hub import SignalHub
from app.layouts.models import ControlPanelSection
from app.layouts.shell import control_panel_shell
from app.pid.biodiesel.hub_factory import build_biodiesel_hub
from app.pid.biodiesel.view import render_biodiesel_pid_svg
from app.pid.sthr.hub_factory import build_sthr_hub
from app.pid.sthr.view import render_sthr_pid_svg

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# FloatingRuntimeManager adapter
# ──────────────────────────────────────────────────────────────
# ``FloatingRuntimeManager.__init__`` requires a ``build_store``
# callable returning an object with ``.bridge`` exposed (legacy
# ``BaseBridgeStore`` shape). The hub IS that shape — ``hub.bridge``
# returns the underlying ``gateway.core.bridge_class.Bridge``. We also
# expose ``.reset()`` for the scenario-change reset hook in
# ``runtime_manager_page.py``: it bumps the hub's snapshot back to
# the seed so the SVG / faceplate land on case-config defaults
# immediately.


class _HubStoreShim:
    """Minimal adapter so :class:`FloatingRuntimeManager` can drive the engine
    via the hub.

    Exposes ``.bridge`` + ``.reset()`` — everything else the runtime
    manager touches is already on the bridge.
    """

    __slots__ = ('_hub',)

    def __init__(self, hub: SignalHub) -> None:
        self._hub = hub

    @property
    def bridge(self) -> Any:
        return self._hub.bridge

    def reset(self) -> None:
        """Reset the simulation.

        Mirrors the legacy :meth:`BaseBridgeStore.reset` semantics
        (bridge reset + snapshot reseed).
        """
        self._hub.engine_control.reset()
        self._hub.reset_snapshot_to_seed()


# ──────────────────────────────────────────────────────────────
# Per-case handler bundle
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CaseHandlers:
    build_hub: Callable[[], SignalHub | None]
    render_svg: Callable[[SignalHub], Any]  # returns html_element
    svg_wrapper_class: str
    process_label: str
    overview_label: str
    pid_label: str


_CASE_HANDLERS: dict[str, CaseHandlers] = {
    'sthr': CaseHandlers(
        build_hub=build_sthr_hub,
        render_svg=render_sthr_pid_svg,
        svg_wrapper_class='sthr-pid-svg',
        process_label='Stirred Tank Heater',
        overview_label='STHR Overview',
        pid_label='Piping and Instrumentation Diagram',
    ),
    'biodiesel': CaseHandlers(
        build_hub=build_biodiesel_hub,
        render_svg=render_biodiesel_pid_svg,
        svg_wrapper_class='biodiesel-pid-svg',
        process_label='Biodiesel Reactor',
        overview_label='Biodiesel Reactor Overview',
        pid_label='Piping and Instrumentation Diagram',
    ),
}


def _available_cases() -> list[str]:
    return sorted(_CASE_HANDLERS.keys())


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────


@ui.page('/control-panel')
def control_panel_index() -> None:
    """Redirect ``/control-panel`` to the first registered case."""
    available = _available_cases()
    default = available[0] if available else 'sthr'
    ui.navigate.to(f'/control-panel/{default}')


def _is_simulation_finished(bridge: Any) -> tuple[bool, str]:
    """Return ``(is_finished, reason)`` for the Run-button block guard.

    The simulation is considered "finished and waiting for the user
    to act" when ALL of the following hold:

    * ``state.natural_stop`` is ``True`` — the worker exited via the
      ``complete`` branch (set in
      ``gateway/bridge_class.py:1559-1565``), not by Stop / error /
      reset.
    * The worker thread is NOT alive — no in-progress run.
    * ``time_end`` is finite — an infinite horizon never "finishes".
    * ``global_sim_time`` has reached (or passed) ``time_end`` within
      the same ``+1e-12`` epsilon the bridge's own ``_is_finished``
      check uses (``gateway/bridge_class.py:1175-1181``).

    Combining all four eliminates false-positives: a freshly Reset
    bridge clears ``natural_stop`` to False (line 988); a Stop press
    leaves the worker dead but with ``natural_stop=False``; a bridge
    with ``time_end=inf`` never trips the block.

    The reason string is wired into the disabled-button ``title``
    attribute (browser-native tooltip) so a hover explains WHY the
    button can't be clicked and what the user should do.

    Returns ``(False, '')`` defensively on any exception so the
    button does NOT get stuck disabled if a state read throws.
    """
    if bridge is None:
        return (False, '')
    try:
        import math

        state = getattr(bridge, 'state', None)
        if state is None:
            return (False, '')
        natural = bool(getattr(state, 'natural_stop', False))
        worker = getattr(bridge, '_worker', None)
        alive = bool(worker is not None and worker.is_alive())
        # ``parse_time_end_value`` is the bridge's own canonical
        # parser (see ``gateway/bridge_class.py:342-362``) — reuse
        # it so a string time_end from a profile load is handled
        # the same way the worker handles it.
        time_end = bridge.parse_time_end_value(
            getattr(state, 'time_end', float('inf')),
        )
        finite = math.isfinite(time_end)
        sim_t = float(getattr(state, 'global_sim_time', 0.0) or 0.0)
        reached = finite and sim_t + 1e-12 >= time_end
    except Exception:
        return (False, '')
    if natural and not alive and reached:
        return (
            True,
            (
                f'Simulation finished at t={sim_t:.4f} min '
                f'(end={time_end:.4f} min). '
                f'Extend End Time or press Reset to continue.'
            ),
        )
    return (False, '')


def _make_engine_button_handlers(
    hub: SignalHub | None,
    svg_wrapper_class: str,  # noqa: ARG001  reserved for future SVG state animation
) -> tuple[Callable, Callable, Callable, Callable]:
    """Build Run / Stop / Reset / Real-Time handlers.

    Every handler is **one-line to the engine** through
    ``hub.engine_control``. Subscribers (SVG / faceplate / modal /
    logger / chart) react asynchronously via the hub's next tick —
    buttons don't fan out themselves.
    """
    bridge = hub.engine_control.bridge if hub is not None else None

    def _on_run() -> None:
        if hub is not None:
            hub.engine_control.run()  # ← one line to engine
        ui.notify('Simulation Started', type='positive', position='bottom-right')
        try:
            from app.hub.data_logger import write_audit_log

            slug = getattr(bridge, 'case_name', 'unknown') if bridge else 'unknown'
            write_audit_log(slug, 'Simulation Started (via Navbar)', bridge=bridge)
        except Exception:
            pass

    def _on_stop() -> None:
        if hub is not None:
            hub.engine_control.stop()  # ← one line to engine
        ui.notify('Simulation Stopped', type='info', position='bottom-right')
        try:
            from app.hub.data_logger import write_audit_log

            slug = getattr(bridge, 'case_name', 'unknown') if bridge else 'unknown'
            write_audit_log(slug, 'Simulation Paused (via Navbar)', bridge=bridge)
        except Exception:
            pass

    def _on_reset() -> None:
        if hub is not None:
            hub.engine_control.reset()  # ← one line to engine
            hub.reset_snapshot_to_seed()
        ui.notify('Simulation Reset', type='info', position='bottom-right')
        try:
            from app.hub.data_logger import write_audit_log

            slug = getattr(bridge, 'case_name', 'unknown') if bridge else 'unknown'
            write_audit_log(slug, 'Simulation Reset (via Navbar)', bridge=bridge)
        except Exception:
            pass

    def _on_realtime(value: bool) -> None:
        if hub is not None:
            hub.engine_control.set_real_time(bool(value))  # ← one line
        ui.notify(
            ('Realtime Simulation Activated' if value else 'Realtime Simulation Deactivated'),
            type='info',
            position='bottom-right',
            timeout=1500,
        )

    return _on_run, _on_stop, _on_reset, _on_realtime


def _build_pid_section(
    handlers: CaseHandlers,
    hub: SignalHub | None,
    case_slug: str,
    on_runtime_manager_click: Callable[[], None] | None = None,
    popout_url: str | None = None,
) -> None:
    """Build the P&ID section into the current NiceGUI context."""
    (
        on_run,
        on_stop,
        on_reset,
        on_realtime,
    ) = _make_engine_button_handlers(
        hub,
        handlers.svg_wrapper_class,
    )
    bridge_state = hub.engine_control.bridge.state if hub is not None else None
    initial_realtime = bool(
        getattr(bridge_state, 'real_time', False) if bridge_state else False,
    )

    with ui.column().classes('main-scroll-wrapper pid-section-root p-0'):
        with ui.column().classes('main-scroll-inner pid-section-inner'):
            # ── Navbar ──
            with ui.row().classes('pid-navbar-row'):
                navbar_cfg = PidNavbarConfig(
                    process_label=handlers.process_label,
                    on_run=on_run,
                    on_stop=on_stop,
                    on_reset=on_reset,
                    on_realtime_change=on_realtime,
                    case_slug=(hub.bridge.case_name if hub is not None else None),
                    initial_realtime=initial_realtime,
                    realtime_bindable=bridge_state,
                    realtime_attr='real_time',
                    on_runtime_manager_click=on_runtime_manager_click,
                    hub=hub,
                    popout_url=popout_url,
                )
                render_pid_navbar(navbar_cfg)

            # ── Faceplate (floating dialog) ──
            # The dialog is built lazily after the modals are
            # registered below, so ``build()`` runs in a context
            # where the full set of ``_modals`` / ``_specs`` is
            # already populated. Constructing it now lets us
            # register it with each modal up front.
            faceplate = FaceplateDialog(
                FaceplateDialogConfig(
                    case_slug=case_slug,
                    bridge=hub.bridge if hub is not None else None,
                ),
            )

            # ── Canvas (no more right drawer) ──
            with ui.row().classes('pid-content pid-canvas-row'):
                if hub is None:
                    ui.label(
                        'Engine not available — hub cannot start.',
                    ).classes('text-white/70 p-4')
                    return

                # Render the SVG via the hub view (uses
                # HubStoreAdapter under the hood so existing
                # modals work unchanged).
                html_element = handlers.render_svg(hub)

                controller_modals: dict[str, Any] = (
                    getattr(
                        html_element,
                        'controller_modals',
                        None,
                    )
                    or {}
                )
                for _tag, modal in controller_modals.items():
                    try:
                        if hasattr(modal, 'set_faceplate'):
                            modal.set_faceplate(faceplate)
                        faceplate.register_modal(modal)
                    except Exception:
                        pass

                # Build the dialog DOM now that the
                # modals are registered. The dialog
                # starts closed; the modal's
                # "Face plate" footer button opens it.
                faceplate.build()

                # ── Wire children ──
                # 1. Faceplate — drives the floating
                #    dialog's bargraphs / numeric labels
                #    each tick.
                faceplate_child = FaceplateChild(hub, faceplate)
                faceplate_child.attach()

                # 2. Modals — refreshes any open dialogs.
                modal_child = ModalChild(hub, controller_modals)
                modal_child.attach()

            # ── UI ↔ engine status sync ──
            # The Run button "active" class and the SVG
            # animation are driven explicitly by the
            # Run/Stop/Reset handlers, but the worker can
            # self-terminate (time_end reached, error, or
            # external stop) without going through those
            # handlers. This timer polls the engine status
            # and resets the UI indicators when the worker
            # transitions out of 'running' on its own, so
            # the operator's view always matches the
            # actual engine state. Mirrors the
            # ``_sync_mode_pill`` pattern at
            # ``app/pages/runtime_manager_page.py:336``.
            if hub is not None:
                _prev_engine_status_holder: dict[str, str] = {
                    'value': '',
                }

                def _sync_engine_status_ui() -> None:
                    try:
                        current = str(
                            hub.engine_control.status or '',
                        )
                    except Exception:
                        return
                    previous = _prev_engine_status_holder['value']
                    if current == previous:
                        return
                    _prev_engine_status_holder['value'] = current

                    # React to implicit terminations
                    # (worker self-stopped on time_end,
                    # or errored). The explicit Run/Stop
                    # handlers already update the UI on
                    # their own, so a transition we missed
                    # is exactly the case we want to fix.
                    if current in ('complete', 'error', 'stopped', 'idle'):
                        if previous == 'running' and current == 'complete':
                            try:
                                ui.notify(
                                    'Simulation reached End Time',
                                    type='info',
                                    position='bottom-right',
                                    timeout=2000,
                                )
                            except Exception:
                                pass
                        elif previous == 'running' and current == 'error':
                            try:
                                ui.notify(
                                    'Simulation stopped (engine error)',
                                    type='warning',
                                    position='bottom-right',
                                    timeout=2000,
                                )
                            except Exception:
                                pass

                ui.html('<style>.svg-wrapper { display: contents; }</style>').classes(
                    'pid-svg-host'
                )

                ui.timer(0.25, _sync_engine_status_ui)

            # ── Start the master tick ──
            # ONE timer per page drives the shared hub. Started after
            # subscribers attach so the first tick already
            # has consumers.
            hub.start()
            ui.timer(hub.tick_s, hub.tick_once)


def _build_monitoring(hub: SignalHub | None, popout_url: str | None = None) -> None:
    """Performance Monitoring section.

    Wraps :func:`render_performance_monitor` from
    ``app/hub/perf_monitor.py`` (moved from
    ``app/components/performance_monitor.py`` during the v1 purge). The
    renderer consumes ``store.bridge._step_log`` directly via its own 50
    ms ``ui.timer`` so it does NOT attach as a :class:`SignalHub`
    subscriber.
    """
    if hub is None:
        with ui.column().classes('control-panel-section-content'):
            ui.label('Performance Monitoring').classes('text-white text-lg')
            ui.label('Engine not available.').classes('text-white/50 text-sm')
        return

    # ``render_performance_monitor`` expects a store-shaped object
    # with a ``.bridge`` attribute. The hub IS that object —
    # ``hub.bridge`` returns the underlying bridge.
    render_performance_monitor(hub, case_slug=hub.bridge.case_name, popout_url=popout_url)


def _build_data_logger(hub: SignalHub | None, popout_url: str | None = None) -> None:
    """Data Logger section.

    Wraps :func:`render_data_logger_section` from
    ``app/hub/data_logger.py`` (moved from
    ``app/pid/_shared/data_logger.py`` during the v1 purge).
    """
    if hub is None:
        data_logger_unavailable(
            'No log entries yet. Connect an engine to start logging data.',
        )
        return

    render_data_logger_section(hub, popout_url=popout_url)


def _build_overview(case_slug: str, handlers: CaseHandlers) -> None:  # noqa: ARG001
    with ui.column().classes('control-panel-section-content'):
        with ui.column().classes('w-full items-center justify-center pt-16 pb-8 gap-4'):
            ui.image('/static/assets/under_construction_v3.png').classes('w-96 opacity-90').style(
                'mix-blend-mode: screen;'
                ' mask-image: radial-gradient('
                'circle, black 50%, transparent 100%);'
                ' -webkit-mask-image: radial-gradient('
                'circle, black 50%, transparent 100%);'
            )
            ui.label('Page Under Construction').classes(
                'text-white/70 text-xl font-bold tracking-wider uppercase'
            )
            ui.label('This section is currently being updated or under maintenance.').classes(
                'text-white/50 text-sm text-center max-w-md'
            )


def _register_case_route(case_slug: str) -> None:
    """Register the per-case ``/control-panel/<case>`` page."""
    handlers = _CASE_HANDLERS[case_slug]

    def page_handler() -> None:
        hub = handlers.build_hub()

        # Stop the hub's tick timer when the client disconnects
        # (page close / navigate away) so the ui.timer doesn't
        # raise "parent slot has been deleted" after the page is gone.
        if hub is not None:
            try:
                from nicegui import context as _ng_context

                _ng_context.client.on_disconnect(lambda: hub.stop())
            except Exception:
                pass

        # Floating Runtime Manager dialog. Only constructed when the
        # engine gateway is importable (i.e. hub is not None) —
        # otherwise the dialog body would just show its own "engine
        # not available" placeholder. The dialog is NOT auto-opened;
        # the navbar Runtime Manager button toggles it.
        #
        # The dialog's Run/Stop action row (rendered by
        # ``runtime_manager_page.py``) is wired to the same
        # ``engine_control`` lifecycle as the navbar buttons. We
        # route through small wrappers so the dialog buttons (a)
        # honor the same finished-block guard the navbar Run uses
        # — extending End Time enables both at the same time — and
        # (b) emit a notify so the user gets the same UX feedback
        # the navbar provides.
        floating_runtime_manager: FloatingRuntimeManager | None = None
        if hub is not None:
            shim = _HubStoreShim(hub)
            bridge_for_guard = hub.engine_control.bridge

            def _dialog_on_run() -> None:
                finished, reason = _is_simulation_finished(bridge_for_guard)
                if finished:
                    ui.notify(
                        reason or 'Simulation already finished.',
                        type='warning',
                        position='bottom-right',
                    )
                    return
                try:
                    hub.engine_control.run()
                except Exception as exc:
                    ui.notify(
                        f'Run failed: {exc}',
                        type='negative',
                        position='bottom-right',
                    )
                    return
                ui.notify(
                    'Simulation Running',
                    type='positive',
                    position='bottom-right',
                )
                try:
                    from app.hub.data_logger import write_audit_log

                    write_audit_log(
                        case_slug,
                        'Simulation Started (via Runtime Manager)',
                        bridge=bridge_for_guard,
                    )
                except Exception:
                    pass

            def _dialog_on_stop() -> None:
                try:
                    hub.engine_control.stop()
                except Exception as exc:
                    ui.notify(
                        f'Stop failed: {exc}',
                        type='negative',
                        position='bottom-right',
                    )
                    return
                ui.notify(
                    'Simulation Stopped',
                    type='info',
                    position='bottom-right',
                )
                try:
                    from app.hub.data_logger import write_audit_log

                    write_audit_log(
                        case_slug,
                        'Simulation Paused (via Runtime Manager)',
                        bridge=bridge_for_guard,
                    )
                except Exception:
                    pass

            floating_runtime_manager = FloatingRuntimeManager(
                case_slug=case_slug,
                process_label=handlers.process_label,
                build_store=lambda s=shim: s,
                on_run=_dialog_on_run,
                on_stop=_dialog_on_stop,
            )

        def _overview_builder() -> None:
            _build_overview(case_slug, handlers)

        def _pid_builder() -> None:
            _build_pid_section(
                handlers,
                hub,
                case_slug=case_slug,
                on_runtime_manager_click=(
                    floating_runtime_manager.toggle
                    if floating_runtime_manager is not None
                    else None
                ),
                popout_url=f'/popout/{case_slug}/pid',
            )

        def _monitoring_builder() -> None:
            _build_monitoring(hub, popout_url=f'/popout/{case_slug}/perf-monitor')

        def _data_logger_builder() -> None:
            _build_data_logger(hub, popout_url=f'/popout/{case_slug}/data-logger')

        sections = (
            ControlPanelSection(
                label=handlers.overview_label,
                builder=_overview_builder,
            ),
            ControlPanelSection(
                label=handlers.pid_label,
                builder=_pid_builder,
            ),
            ControlPanelSection(
                label='Performance Monitoring',
                builder=_monitoring_builder,
            ),
            ControlPanelSection(
                label='Data Logger',
                builder=_data_logger_builder,
            ),
        )
        control_panel_shell(
            sections=sections,
            default_section=handlers.overview_label,
            storage_key=f'last_section_{case_slug}',
        )

    # Register the route under the per-case URL.
    ui.page(f'/control-panel/{case_slug}')(page_handler)


# Register a route for every case. New cases added to
# ``_CASE_HANDLERS`` are picked up automatically on next reload.
for _slug in _available_cases():
    _register_case_route(_slug)


__all__ = [
    'CaseHandlers',
    'control_panel_index',
]
