# app/components/pid_navbar.py

"""PID navigation bar — ported from engine_root.

Behavior preserved:
- Process label on the left
- Runtime Manager + Real Time checkbox on the right
- Run / Stop / Reset stack buttons
- Day/date + time clock on the far right

The Runtime Manager button opens a child window with the runtime
manager page (mirrors the Runtime Manager card in ``tests/main.py``)
where the user can edit units, step size, end time, acceleration,
real-time mode, controller / loop modes and scenario. The Real Time
checkbox in the navbar shares the same backing flag as the Real Time
checkbox inside the Runtime Manager page — toggling either one
updates the bridge's ``state.real_time``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

from nicegui import ui

from app.ui.button_feedback import apply_feedback_classes

# Buttons on the PID navbar render against the dark control-panel
# surface, so we attach the dark variant of the feedback CSS class.
NAVBAR_BUTTON_VARIANT = 'dark'


@dataclass(frozen=True)
class PidNavbarConfig:
    process_label: str
    on_run: Callable[[], None]
    on_stop: Callable[[], None]
    on_reset: Callable[[], None]
    on_realtime_change: Callable[[bool], None]
    # Slug used to route the Runtime Manager child window to the right
    # case page (e.g. ``'sthr'`` or ``'biodiesel'``). When ``None`` the
    # button falls back to using ``process_label`` (legacy behavior).
    case_slug: str | None = None
    # Initial value for the navbar Real Time checkbox. The control
    # itself is the source of truth in this widget — the page builder
    # passes the bridge's current ``state.real_time`` so the navbar
    # reflects the live setting on first render.
    initial_realtime: bool = False
    # Optional bindable target for two-way binding of the Real Time
    # checkbox. When provided, the navbar checkbox is bound via
    # ``bind_value(realtime_bindable, realtime_attr)`` so toggles in
    # other windows (e.g. the Runtime Manager) propagate back to the
    # navbar without a manual refresh.
    realtime_bindable: Any | None = None
    realtime_attr: str = 'real_time'
    # Optional callback for the Runtime Manager button. When set, the
    # button invokes this callback (e.g. to toggle a floating dialog
    # mounted on the same page) instead of opening a child browser
    # window at `/runtime-manager/<case>`. When `None` the legacy
    # window-open behavior is preserved.
    on_runtime_manager_click: Callable[[], None] | None = None
    # Optional hub instance to enable direct UI synchronization (e.g., Run
    # button state).
    hub: Any | None = None
    # Optional URL for the pop-out button.
    popout_url: str | None = None


def render_process_label(process_label: str) -> None:
    ui.label(process_label).classes('pid-navbar-process-label')


def open_hmi_window(
    url: str,
    name: str,
    width: int = 1100,
    height: int = 720,
) -> None:
    """Open HMI child window with controlled size."""
    ui.run_javascript(f"""
        const width = {width};
        const height = {height};

        const left = Math.round((screen.availWidth - width) / 2);
        const top = Math.round((screen.availHeight - height) / 2);

        const win = window.open(
            "{url}",
            "{name}",
            [
                `width=${{width}}`,
                `height=${{height}}`,
                `left=${{left}}`,
                `top=${{top}}`,
                "resizable=yes",
                "scrollbars=no",
                "menubar=no",
                "toolbar=no",
                "location=no",
                "status=no"
            ].join(",")
        );

        if (win) {{
            win.focus();
        }}
    """)


def render_runtime_manager(
    config: PidNavbarConfig,
) -> None:
    # Route to the per-case runtime manager page. ``case_slug`` (e.g.
    # ``'sthr'``) is the canonical key; fall back to the process label
    # so legacy callers without a slug still open *something*.
    route_key = config.case_slug or config.process_label
    runtime_manager_url = f'/runtime-manager/{quote(route_key, safe="")}'

    # Prefer the host-supplied callback (e.g. toggle a floating
    # dialog on the same page). Fall back to opening a child
    # window — preserves the legacy behavior for callers that
    # don't pass ``on_runtime_manager_click``.
    if config.on_runtime_manager_click is not None:
        button_click_handler = config.on_runtime_manager_click
    else:

        def button_click_handler():
            open_hmi_window(
                runtime_manager_url,
                'RuntimeManagerWindow',
                1100,
                720,
            )

    with ui.column().classes('pid-navbar-manager-block'):
        manager_button = ui.button(
            color=None,
            on_click=button_click_handler,
        )
        manager_button.props('flat no-caps dense').classes('pid-navbar-manager-btn')
        with manager_button:
            ui.image('/static/assets/icons/chart_time.svg').classes(
                'pid-navbar-manager-symbol'
            ).props('fit=contain no-spinner')

            ui.label('Runtime Manager').classes('pid-navbar-manager-label')

        # Sub-16 ms click feedback on the Runtime Manager toggle.
        # ``apply_feedback_classes`` adds the dark variant
        # classes; ``attach_pointer_feedback`` installs the
        # pointerdown/pointerup listeners.
        apply_feedback_classes(manager_button, variant=NAVBAR_BUTTON_VARIANT)

        def _on_realtime_change(e: Any) -> None:
            config.on_realtime_change(bool(e.value))
            # Persist so the toggle survives a page reload.
            try:
                from nicegui import app as _nicegui_app

                slug = config.case_slug or config.process_label
                _nicegui_app.storage.user[f'rt_toggle_{slug}'] = bool(e.value)
            except Exception:
                pass
            try:
                from app.hub.data_logger import write_audit_log

                slug = config.case_slug or config.process_label
                state = 'ON' if e.value else 'OFF'
                write_audit_log(slug, f'User turned Real-Time Mode {state}')
            except Exception:
                pass

        # Restore persisted Real-Time toggle state if available.
        _rt_initial = config.initial_realtime
        try:
            from nicegui import app as _nicegui_app

            _slug = config.case_slug or config.process_label
            _stored_rt = _nicegui_app.storage.user.get(f'rt_toggle_{_slug}')
            if _stored_rt is not None:
                _rt_initial = bool(_stored_rt)
        except Exception:
            pass

        checkbox = (
            ui.checkbox(
                'Real Time',
                value=_rt_initial,
                on_change=_on_realtime_change,
            )
            .props('dense color=white keep-color')
            .classes('pid-navbar-realtime-check')
        )

        # When the page has a bindable real_time flag (the bridge's
        # ``BridgeState``), bind the checkbox two-way so the widget
        # reflects updates made elsewhere — e.g. the Runtime Manager
        # window toggling Real Time updates ``bridge.state.real_time``,
        # which NiceGUI's binding system propagates back here.
        if config.realtime_bindable is not None:
            try:
                checkbox.bind_value(
                    config.realtime_bindable,
                    config.realtime_attr,
                )
            except Exception:
                # Falling back silently keeps the widget usable even
                # when the bindable target is not a bindable_dataclass
                # (e.g. an upcoming dataclass that hasn't been migrated).
                pass


def render_simulation_control_buttons(config: PidNavbarConfig) -> None:
    with ui.row().classes('pid-navbar-control-group items-center no-wrap'):
        run_button = ui.button(
            'Run',
            icon='play_arrow',
            color=None,
            on_click=config.on_run,
        )
        run_button.props('flat no-caps dense stack').classes(
            'pid-navbar-action-btn pid-navbar-run-btn'
        )
        if config.hub is not None and hasattr(config.hub, 'ui_sync'):
            hub = config.hub
            bridge = getattr(hub, 'bridge', None)
            if bridge is not None:
                hub.ui_sync.register_class_toggle(
                    run_button,
                    'pid-navbar-run-btn-active',
                    lambda b=bridge: getattr(b.state, 'status', 'idle') in ('running', 'starting'),
                )
        apply_feedback_classes(run_button, variant=NAVBAR_BUTTON_VARIANT)

        stop_button = ui.button(
            'Stop',
            icon='stop',
            color=None,
            on_click=config.on_stop,
        )
        stop_button.props('flat no-caps dense stack').classes(
            'pid-navbar-action-btn pid-navbar-stop-btn'
        )
        apply_feedback_classes(stop_button, variant=NAVBAR_BUTTON_VARIANT)

        reset_button = ui.button(
            'Reset',
            icon='restart_alt',
            color=None,
            on_click=config.on_reset,
        )
        reset_button.props('flat no-caps dense stack').classes(
            'pid-navbar-action-btn pid-navbar-reset-btn'
        )
        apply_feedback_classes(reset_button, variant=NAVBAR_BUTTON_VARIANT)


def render_clock() -> None:
    with ui.column().classes('pid-navbar-clock'):
        day_date_label = ui.label().classes('pid-navbar-clock-date')
        time_label = ui.label().classes('pid-navbar-clock-time')

    def update_clock() -> None:
        now = datetime.now()
        day_date_label.set_text(now.strftime('%A, %d %B %Y'))
        time_label.set_text(now.strftime('%H:%M:%S'))

    update_clock()
    ui.timer(1.0, update_clock)


def render_navbar_separator() -> None:
    with ui.row().classes('pid-navbar-separator-wrap'):
        ui.separator().props('vertical').classes('pid-navbar-separator')


def render_pid_navbar(config: PidNavbarConfig) -> None:
    with ui.row().classes('pid-navbar items-center no-wrap'):
        with ui.row().classes('pid-navbar-left items-center no-wrap'):
            render_process_label(config.process_label)

        with ui.row().classes('pid-navbar-right items-center justify-end no-wrap'):
            render_runtime_manager(config)
            render_navbar_separator()
            render_simulation_control_buttons(config)
            render_navbar_separator()
            render_clock()
            if config.popout_url:
                render_navbar_separator()
                from app.components.popout_button import render_popout_button

                render_popout_button(config.popout_url)
