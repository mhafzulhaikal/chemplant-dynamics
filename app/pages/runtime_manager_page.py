# app/pages/runtime_manager_page.py

"""Runtime Manager card body — DCS faceplate styling.

Exposes runtime parameters (Units, Step Size, End Time, Acceleration,
Loop modes, Scenario) as a floating card mounted inside
:mod:`app.components.floating_runtime_manager`.

Controls drive the bridge directly so changes are immediately visible to
the dashboard.

Styling reuses ``runtime-manager-page-*`` CSS classes
(``app/static/css/runtime_manager_page.css``). Floating-specific
overrides (``position: fixed``, drag-handle cursor, snap-to-edge glow,
minimize state) also live in the same stylesheet under ``.floating-
runtime-manager-card``.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

# pyrefly: ignore [missing-import]
from nicegui import ui

from app.pages._runtime_manager_helpers import (
    MODE_PILL_CLASSES,
)
from app.pages._runtime_manager_helpers import (
    apply_mode_to_controller_and_loops as _apply_mode_to_controller_and_loops,
)
from app.pages._runtime_manager_helpers import (
    default_loop_mode_for_scenario as _default_loop_mode_for_scenario,
)
from app.pages._runtime_manager_helpers import (
    event_value as _event_value,
)
from app.pages._runtime_manager_helpers import (
    mode_pill_class as _mode_pill_class,
)
from app.pages._runtime_manager_helpers import (
    mode_pill_label as _mode_pill_label,
)
from app.pages._runtime_manager_helpers import (
    normalize_mode_for_ui as _normalize_mode_for_ui,
)
from app.pages._runtime_manager_helpers import (
    safe_text_bind as _render_bind_text,
)
from app.pages._runtime_manager_helpers import (
    short_unit_label as _short_unit_label,
)

logger = logging.getLogger(__name__)


# ── Page builder ──


def render_runtime_manager_body(
    case_cfg: Any,
    bridge: Any,
    store: Any,
    process_label: str,
    *,
    on_close: Callable[[], None] | None = None,
    on_minimize: Callable[[], None] | None = None,
    is_dialog_open: Callable[[], bool] | None = None,
    is_minimized: Callable[[], bool] | None = None,
    on_minimize_button_ready: Callable[..., None] | None = None,
    on_run: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
) -> None:
    """Render the Runtime Manager card body.

    Pure UI: takes a case config, a bridge, and a store, and writes
    the card directly into the *current* NiceGUI context. No parent
    assumptions, no implicit page wrapping — that makes it reusable
    from:

    * The standalone ``/runtime-manager/<case>`` page (wrapped in a
      centered, full-viewport shell).
    * The floating draggable dialog mounted on the control-panel
      page itself.

    ``on_close`` is an optional callback invoked when the user clicks
    the close (×) button in the card header. The standalone page
    passes ``None`` (no header close button) and the floating dialog
    passes a hide-the-dialog handler.

    ``on_minimize`` is an optional callback invoked when the user
    clicks the minimize (−) button in the floating card header.
    The standalone page passes ``None`` (no header minimize button)
    and the floating dialog passes a collapse-the-body handler.

    ``is_minimized`` is an optional callable returning the *current*
    minimize state — read once at render time to pick the initial
    button icon/tooltip. Optional because the standalone page never
    minimizes.

    ``on_minimize_button_ready`` is an optional registration hook
    called with ``(button, tooltip)`` after the minimize button is
    built. The floating dialog uses this to keep the icon and
    tooltip text in sync with the server-side minimize state across
    toggle cycles. The standalone page passes ``None``.

    ``on_run`` and ``on_stop`` are optional callbacks that render an
    EXECUTION-section action row with Continue (or Run when the sim
    is fresh) and Stop buttons. The same Run/Stop semantics as the
    PID navbar — wired by the floating dialog to
    ``hub.engine_control.run`` / ``hub.engine_control.stop`` so the
    user can pause and continue without bouncing back to the navbar.
    When ``on_run`` is ``None`` the action row is omitted entirely
    (standalone page behaviour).
    """
    _render_runtime_manager_card(
        case_cfg=case_cfg,
        bridge=bridge,
        store=store,
        process_label=process_label,
        on_close=on_close,
        on_minimize=on_minimize,
        is_dialog_open=is_dialog_open,
        is_minimized=is_minimized,
        on_minimize_button_ready=on_minimize_button_ready,
        on_run=on_run,
        on_stop=on_stop,
    )


def _render_section(
    title: str,
    hint: str = '',
) -> Any:
    """Open a DCS section card and return the body container for fields.

    The returned element is a grid container (12 columns) that
    :func:`_render_field` places its fields into. The caller is
    responsible for closing the section (via the context manager's
    ``__exit__``). Layout:

    +----------------------------------------+ |  SECTION TITLE
    hint     | +----------------------------------------+ |  [ field ] [
    field ] [ field ]         | |  [ field-wide                 ]
    | +----------------------------------------+
    """
    with ui.element('div').classes('runtime-manager-section'):
        with ui.element('div').classes('runtime-manager-section-header'):
            ui.label(title).classes('runtime-manager-section-title')
            if hint:
                ui.label(hint).classes('runtime-manager-section-hint')
        return ui.element('div').classes('runtime-manager-section-body')


def _render_field(
    _body: Any,
    label: str,
    *,
    span: int = 4,
    unit: str = '',
) -> Any:
    """Open a faceplate field inside ``body`` and return the field row.

    The caller then places the actual input / readout into the
    returned row. ``span`` selects how many grid columns the field
    occupies (4 = third, 6 = half, 12 = full).
    """
    span_class = (
        'runtime-manager-field-full'
        if span >= 12
        else ('runtime-manager-field-wide' if span >= 6 else 'runtime-manager-field')
    )
    with ui.element('div').classes(span_class):
        ui.label(label).classes('runtime-manager-field-label')
        row = ui.element('div').classes('runtime-manager-field-row')
        if unit:
            with row:
                # Caller's input goes between the row and the unit chip
                # — we leave the unit chip to the caller to append via
                # ``unit_chip()``.
                pass
        return row


def _render_unit_chip(row: Any, unit: str) -> None:
    """Append a unit suffix chip to a previously-opened field row."""
    chip_text = _short_unit_label(unit)
    if not chip_text:
        return
    with row:
        ui.label(chip_text).classes('runtime-manager-field-unit')


def _render_readout(row: Any, *, small: bool = False) -> Any:
    """Append a digital readout (display-only) into ``row``.

    Returns the label element so the caller can ``bind_text_from`` it.
    """
    cls = (
        'runtime-manager-readout runtime-manager-readout-sm' if small else 'runtime-manager-readout'
    )
    with row:
        return ui.label('—').classes(cls)


def _render_runtime_manager_card(
    case_cfg: Any,
    bridge: Any,
    store: Any,
    process_label: str,
    *,
    on_close: Callable[[], None] | None = None,
    on_minimize: Callable[[], None] | None = None,
    is_dialog_open: Callable[[], bool] | None = None,
    is_minimized: Callable[[], bool] | None = None,
    on_minimize_button_ready: Callable[..., None] | None = None,
    on_run: Callable[[], None] | None = None,
    on_stop: Callable[[], None] | None = None,
) -> None:
    """Render the Runtime Manager card.

    All controls drive ``bridge.state.*`` and call
    ``bridge.apply_runtime_configuration`` on change so the simulation
    worker picks up the new values immediately. The card chrome and
    field styling reuse the ``runtime-manager-page-*`` classes (see
    module docstring) so the page reads like the controller modal — same
    border, fonts, and translucent field controls.
    """
    case_runtime = getattr(case_cfg, 'CASE_RUNTIME', None)

    case_default_mode = str(getattr(case_runtime, 'default_mode', 'automatic'))
    case_default_mode_display = (
        case_default_mode
        if any(ch.isupper() for ch in case_default_mode)
        else case_default_mode.capitalize()
    )

    case_default_unit = case_cfg.normalize_time_unit(
        getattr(
            case_runtime,
            'time_unit',
            case_cfg.SIMULATION_PARAMS.get('time_unit', 'minutes'),
        ),
    )

    if not str(bridge.state.controller_mode or '').strip():
        bridge.state.controller_mode = case_default_mode_display

    def record_info(message: str, *, mode: str | None = None) -> None:
        try:
            bridge.queue_status(
                message,
                mode=mode or bridge.state.controller_mode,
            )
        except Exception:
            pass

    # Forward-declared refs so the scenario handler can clear the End
    # Time field after the implicit reset. The strip-chart from
    # tests/main.py is not part of this page (the dashboard already
    # owns plotting).
    ui_refs: dict[str, Any] = {'end_input': None}

    def _do_reset_simulation() -> None:
        """Internal reset triggered by scenario changes.

        Note: this is *not* exposed as a user-facing button on this
        page — the navbar Run / Stop / Reset stack owns those actions.
        Scenario changes still need to reset the simulation so the
        new initial condition x₀ takes effect on the next step.
        """
        try:
            store.reset()
            end_input_ref = ui_refs.get('end_input')
            if end_input_ref is not None:
                end_input_ref.value = ''
            record_info('Simulation reset (scenario change)')
        except Exception as exc:
            ui.notify(
                f'Failed to reset simulation: {exc}',
                color='negative',
            )

    # ── Card chrome (DCS faceplate) ──
    with ui.card().classes('w-full runtime-manager-page-card'):
        # Header strip: tag chip + title block on the left, mode
        # pill on the right, and (optionally) window controls
        # (minimize / close) on the far right. The header row is
        # the drag handle in the floating context.
        with ui.row().classes('runtime-manager-page-header no-wrap'):
            with ui.column().classes('runtime-manager-page-title-block'):
                ui.label('RUNTIME MANAGER').classes('runtime-manager-page-title')

                # Use SIM-RTM and the process label as the sub-title
                # (consistent with faceplate subtitle styling)
                title_text = f'SIM-RTM — {process_label}'.upper() if process_label else 'SIM-RTM'
                ui.label(title_text).classes('runtime-manager-page-process-label')

            with ui.row().classes('runtime-manager-page-header-right no-wrap'):
                # Live mode-quality pill. We bind the text to
                # ``bridge.state.controller_mode`` and use a small
                # server-side poll timer to refresh the color class
                # — NiceGUI doesn't have a class-binding primitive,
                # so a 250 ms poll on this single label is the
                # cheapest way to keep the pill color in sync with
                # the underlying mode.
                def _apply_pill_classes(target: Any, mode_value: Any) -> None:
                    try:
                        target.classes(remove=' '.join(MODE_PILL_CLASSES))
                        target.classes(add=_mode_pill_class(mode_value))
                    except Exception:
                        pass

                mode_pill = ui.label(_mode_pill_label(bridge.state.controller_mode)).classes(
                    f'runtime-manager-status-pill {_mode_pill_class(bridge.state.controller_mode)}'
                )
                mode_pill.bind_text_from(
                    bridge.state,
                    'controller_mode',
                    backward=lambda value: _mode_pill_label(value),
                )
                _apply_pill_classes(mode_pill, bridge.state.controller_mode)

                def _sync_mode_pill() -> None:
                    # If the body is mounted inside a dialog, gate
                    # the timer on the dialog being open. When the
                    # dialog is closed, the dialog's slot children
                    # are still in the DOM (the ``q-dialog`` Vue
                    # component only toggles its wrapper's
                    # visibility — see NiceGUI's ``dialog.py:14-29``),
                    # so a 250 ms timer continues to fire and would
                    # call ``_apply_pill_classes`` on ``mode_pill``
                    # with the same element NiceGUI may be
                    # internally re-rendering. If the ``mode_pill``
                    # reference is stale at that moment, the
                    # ``target.classes(remove=...)`` call can throw
                    # a Vue warning and trigger a slot re-render
                    # mid-transition, which is what previously
                    # caused the card to flash invisible on
                    # reopen. Gating on ``is_dialog_open`` makes
                    # the timer a no-op while the dialog is
                    # closed and avoids the race entirely.
                    #
                    # When ``is_dialog_open`` is ``None`` (the
                    # standalone page context, where there is no
                    # surrounding dialog), the timer always runs.
                    if is_dialog_open is not None and not is_dialog_open():
                        return
                    _apply_pill_classes(mode_pill, bridge.state.controller_mode)

                ui.timer(0.25, _sync_mode_pill)

                # Optional minimize / close buttons — only emitted when
                # the body is rendered inside a container (e.g. the
                # floating dialog) that wants to dismiss itself. The
                # standalone page passes ``on_close=None`` and gets
                # nothing.
                if on_minimize is not None:
                    # Initial state. ``is_minimized`` is None on the
                    # standalone page (which never shows a minimize
                    # button anyway), so default to "not minimized"
                    # (icon ``horizontal_rule``, tooltip "Minimize").
                    initially_minimized = bool(
                        is_minimized() if is_minimized is not None else False
                    )
                    initial_icon = 'crop_square' if initially_minimized else 'horizontal_rule'
                    initial_label = 'Restore' if initially_minimized else 'Minimize'
                    min_btn = (
                        ui.button(
                            icon=initial_icon,
                            color=None,
                            on_click=on_minimize,
                        )
                        .props(f'flat dense size=sm aria-label="{initial_label}"')
                        .classes('runtime-manager-window-btn')
                    )
                    # Single, idempotently-updatable tooltip — the
                    # ``ui.tooltip`` element exposes a ``.text``
                    # setter that the FloatingRuntimeManager can
                    # rewrite when the minimize state flips. Using
                    # ``ui.button.tooltip(...)`` would APPEND a new
                    # ``q-tooltip`` slot child on every call instead
                    # of rewriting the existing one — confirmed by
                    # reading NiceGUI's ``element.py`` tooltip helper.
                    with min_btn:
                        min_tooltip = ui.tooltip(initial_label)
                    if on_minimize_button_ready is not None:
                        try:
                            on_minimize_button_ready(min_btn, min_tooltip)
                        except TypeError:
                            # Backwards-compatible single-arg form.
                            on_minimize_button_ready(min_btn)

                if on_close is not None:
                    ui.button(
                        icon='close',
                        color=None,
                        on_click=on_close,
                    ).props('flat dense size=sm').classes(
                        'runtime-manager-window-btn runtime-manager-window-btn-close'
                    )

        # ── Hero timer strip (Current Time) ──
        # The big DCS-style clock lives at the top of the card, just
        # under the header, instead of buried inside the TIME BASE
        # section. The label is amber, the value is a 22 px monospace
        # readout bound to ``bridge.state.global_sim_time``, and a
        # smaller amber unit suffix on the right flips with the
        # Units selector.
        with ui.element('div').classes('runtime-manager-timer'):
            with ui.element('div').classes('runtime-manager-timer-block'):
                ui.label('Current Time').classes('runtime-manager-timer-label')
                hero_current_time_label = ui.label('0.0000').classes('runtime-manager-timer-value')
            hero_unit_label = ui.label(case_default_unit).classes('runtime-manager-timer-unit')

        # ── Form body ──
        # ``runtime-manager-page-form`` supplies the row gap,
        # vertical scroll, and 1rem padding that the modal CSS
        # establishes. The existing rule targets a div, not a
        # NiceGUI column, so use ``ui.element('div')`` here.
        with ui.element('div').classes('runtime-manager-page-form'):
            # ── Section: TIME BASE ──
            time_body = _render_section(
                'TIME BASE',
                hint='integration step & horizon',
            )

            with time_body:
                # Units selector — a faceplate "display" field that
                # drives all numeric conversions in the section.
                units_row = _render_field(time_body, 'Units', span=4)
                with units_row:
                    units_select = (
                        ui.select(
                            ['seconds', 'minutes', 'hours'],
                            value=case_default_unit,
                            on_change=None,  # wired below
                        )
                        .props('dense borderless popup-content-class="runtime-manager-mode-popup"')
                        .classes('runtime-manager-page-input runtime-manager-page-select')
                    )
                _render_unit_chip(units_row, '')

                # Step size
                step_row = _render_field(time_body, 'Step Size', span=4)
                with step_row:
                    step_input = (
                        ui.number(
                            format='%.4f',
                            min=0.0001,
                            step=0.001,
                        )
                        .props('color="amber"')
                        .classes('runtime-manager-page-input runtime-manager-page-select')
                    )
                    step_input.bind_value_from(
                        bridge.state,
                        'Ts',
                        backward=lambda ts: float(
                            case_cfg.from_minutes(
                                float(ts) if ts is not None else 0.01,
                                units_select.value,
                            )
                        ),
                    )

                _render_unit_chip(step_row, '')

                # End Time
                end_row = _render_field(time_body, 'End Time', span=4)
                with end_row:
                    end_input = (
                        ui.input(
                            placeholder='Inf',
                        )
                        .props('color="amber"')
                        .classes('runtime-manager-page-input runtime-manager-page-select')
                    )
                    end_input.bind_value_from(
                        bridge.state,
                        'time_end',
                        backward=lambda te: (
                            ''
                            if (te is None or math.isinf(bridge.parse_time_end_value(te)))
                            else f'{case_cfg.from_minutes(float(te), units_select.value):g}'
                        ),
                    )
                ui_refs['end_input'] = end_input
                _render_unit_chip(end_row, '')

            # ── Section: EXECUTION ──
            exec_body = _render_section(
                'EXECUTION',
                hint='pacing factor',
            )

            with exec_body:
                # Acceleration
                accel_row = _render_field(exec_body, 'Acceleration', span=4)
                with accel_row:
                    accel_input = (
                        ui.number(
                            format='%.2f',
                            min=0.000001,
                            max=1000.0,
                            step=0.1,
                        )
                        .props('color="amber"')
                        .classes('runtime-manager-page-input runtime-manager-page-select')
                    )
                    accel_input.bind_value_from(bridge.state, 'acceleration')
                # Removed unit chip '×' per user request

                # Acceleration hint removed per user request

            # ── Action row: Continue / Stop (floating dialog only) ──
            # Mirrors the navbar Run/Stop buttons so the user can pause
            # and continue a paused simulation without bouncing back to
            # the PID navbar. The standalone page omits this row
            # (``on_run`` is None there). The label is "Continue" when
            # the worker is dead (paused or finished), "Run" when the
            # worker has never started. We pick the label fresh on
            # every render — the floating dialog re-builds the body
            # whenever it re-opens, so a stale label is impossible
            # for the standalone case and the dialog case both.
            if on_run is not None:
                with ui.element('div').classes(
                    'runtime-manager-section runtime-manager-actions-section',
                ):
                    with ui.element('div').classes(
                        'runtime-manager-section-header',
                    ):
                        ui.label('ACTIONS').classes(
                            'runtime-manager-section-title',
                        )
                        ui.label('run / pause from here').classes(
                            'runtime-manager-section-hint',
                        )
                    with ui.element('div').classes(
                        'runtime-manager-section-body runtime-manager-actions-row',
                    ):
                        # Always label the primary action "Continue"
                        # — the operator thinks in "continue / stop"
                        # terms regardless of whether this is the
                        # first run or a resume.
                        run_btn = (
                            ui.button(
                                'Continue',
                                icon='play_arrow',
                                color=None,
                                on_click=on_run,
                            )
                            .props(
                                'flat no-caps dense aria-label="Continue simulation"',
                            )
                            .classes(
                                'runtime-manager-action-btn runtime-manager-action-btn-run',
                            )
                        )
                        with run_btn:
                            ui.tooltip(
                                'Continue the simulation. '
                                'Disabled until you extend End Time or '
                                'Reset when the previous run finished.',
                            )

                        if on_stop is not None:
                            stop_btn = (
                                ui.button(
                                    'Stop',
                                    icon='stop',
                                    color=None,
                                    on_click=on_stop,
                                )
                                .props(
                                    'flat no-caps dense aria-label="Pause simulation"',
                                )
                                .classes(
                                    'runtime-manager-action-btn runtime-manager-action-btn-stop',
                                )
                            )
                            with stop_btn:
                                ui.tooltip(
                                    'Pause the simulation. Press Continue to resume.',
                                )

            # ── Section: LOOP MODES (multi-loop cases only) ──
            loop_order = getattr(case_cfg, 'LOOP_ORDER', None)
            loop_mode_select_refs: dict[str, Any] = {}
            loop_displays: dict[str, Any] = {}

            def _apply_mode(mode: str) -> None:
                """Apply ``mode`` to the bridge's global controller_mode and
                every per-loop mode, syncing visible loop selects.

                Thin wrapper that pre-binds the loop-section locals
                (``bridge``, ``case_cfg``, ``loop_mode_select_refs``,
                ``loop_displays``) so UI handlers can call it with a
                single ``mode`` argument. Renamed from the prior
                ``_apply_mode_to_controller_and_loops`` so it no longer
                shadows the imported module-level helper of the same
                name (which was the cause of Pylance reportCallIssue and
                an outright runtime infinite recursion when the wrapper
                called itself).
                """
                _apply_mode_to_controller_and_loops(
                    bridge,
                    case_cfg,
                    mode,
                    loop_mode_select_refs,
                    loop_displays,
                )

            if loop_order and len(loop_order) > 1:
                loops_body = _render_section(
                    'LOOP MODES',
                    hint='per-controller mode',
                )

                # Force flex-row layout so all loops stay on one row with even
                # spacing
                loops_body.style(
                    'display: flex !important; '
                    'flex-direction: row !important; '
                    'justify-content: space-between !important; '
                    'flex-wrap: nowrap !important; '
                    'grid-template-columns: none !important;'
                )

                with loops_body:
                    for loop in loop_order:
                        current_mode = _normalize_mode_for_ui(
                            bridge,
                            bridge.state.loop_modes.get(
                                loop,
                                bridge.state.controller_mode or 'Automatic',
                            ),
                        )
                        # Loop name on top, mode pill (DCS style) on the
                        # right; clicking the pill cycles to the next
                        # supported mode — same affordance as a
                        # "push to advance" button on a real DCS
                        # faceplate.
                        with (
                            ui.element('div')
                            .classes('runtime-manager-field')
                            .style('flex: 1 1 0; grid-column: auto; min-width: 0;')
                        ):
                            ui.label(loop).classes('runtime-manager-field-label')
                            loop_row = ui.element('div').classes('runtime-manager-field-row')
                            with loop_row:
                                pill_cls = 'runtime-manager-status-pill ' + _mode_pill_class(
                                    current_mode
                                )
                                pill = ui.label(_mode_pill_label(current_mode)).classes(pill_cls)
                                pill.style('cursor: pointer;')

                                def _cycle_mode(_p=pill, loop_name=loop) -> None:
                                    supported = list(bridge.supported_modes() or [])
                                    current = _normalize_mode_for_ui(
                                        bridge,
                                        bridge.state.loop_modes.get(
                                            loop_name,
                                            bridge.state.controller_mode or 'Automatic',
                                        ),
                                    )
                                    try:
                                        idx = supported.index(current)
                                    except ValueError:
                                        idx = 0
                                    new_mode = (
                                        supported[(idx + 1) % len(supported)]
                                        if supported
                                        else current
                                    )
                                    bridge.state.loop_modes[loop_name] = new_mode
                                    bridge.apply_runtime_configuration(restart_if_needed=True)
                                    bridge.persist_profile()
                                    record_info(f'{loop_name} mode: {new_mode}')

                                pill.on('click', _cycle_mode)
                                loop_displays[loop] = pill

                    def _sync_all_loop_modes() -> None:
                        if is_dialog_open is not None and not is_dialog_open():
                            return
                        for loop_id, pill_el in loop_displays.items():
                            current_mode = _normalize_mode_for_ui(
                                bridge,
                                bridge.state.loop_modes.get(
                                    loop_id,
                                    bridge.state.controller_mode or 'Automatic',
                                ),
                            )
                            new_text = _mode_pill_label(current_mode)
                            if getattr(pill_el, 'text', None) != new_text:
                                pill_el.text = new_text
                            _apply_pill_classes(pill_el, current_mode)

                    ui.timer(0.25, _sync_all_loop_modes)

            # ── Section: INITIAL CONDITION ──
            scenario_order = getattr(case_cfg, 'SCENARIO_ORDER', None)
            # Pre-declare so the status-bar reference below is provably
            # bound even when ``scenario_order`` is falsy (in which case
            # the status bar falls back to the em-dash placeholder).
            current_scenario_label: str | None = None
            # Same trick for ``scenario_labels``: the status-bar
            # ``backward`` lambda below closes over it and may be invoked
            # even when ``scenario_order`` is empty, so we pre-declare an
            # empty mapping and populate it inside the guarded branch.
            scenario_labels_map: dict[str, str] = {}
            if scenario_order:
                scenario_labels = {
                    'startup': 'Start-up',
                    'operational': 'Normal Operation',
                    'shutdown': 'Shutdown',
                }
                # Mirror into the pre-declared closure target so the
                # status-bar ``backward`` lambda below is provably
                # bound even when ``scenario_order`` is empty.
                scenario_labels_map.update(scenario_labels)
                scenario_options = [
                    scenario_labels.get(scenario, scenario.capitalize())
                    for scenario in scenario_order
                ]
                scenario_value_to_key = {
                    scenario_labels.get(key, key.capitalize()): key for key in scenario_order
                }

                def _on_scenario_change(event: Any) -> None:
                    selected_label = str(
                        _event_value(event, 'Normal Operation') or 'Normal Operation',
                    )
                    scenario_key = scenario_value_to_key.get(
                        selected_label,
                        'operational',
                    )
                    scenario_loop_mode = _default_loop_mode_for_scenario(
                        bridge,
                        scenario_key,
                    )

                    bridge.state.scenario = scenario_key
                    bridge.state.input_overrides = {}

                    _apply_mode(scenario_loop_mode)

                    bridge.apply_runtime_configuration(restart_if_needed=False)
                    _do_reset_simulation()
                    bridge.persist_profile()

                    record_info(
                        f'Scenario set to: {selected_label} '
                        f'(all modes set to {scenario_loop_mode})',
                    )
                    try:
                        from app.hub.data_logger import write_audit_log

                        slug = getattr(bridge, 'case_name', 'unknown')
                        write_audit_log(
                            slug,
                            f'User changed Scenario to {selected_label}',
                            bridge=bridge,
                        )
                    except Exception:
                        pass

                current_scenario = (
                    str(
                        bridge.state.scenario or 'operational',
                    )
                    .strip()
                    .lower()
                )
                current_scenario_label = scenario_labels.get(
                    current_scenario,
                    current_scenario.capitalize(),
                )
                if current_scenario_label not in scenario_options:
                    current_scenario_label = (
                        scenario_labels.get('operational', 'Normal Operation')
                        if 'operational' in scenario_order
                        else scenario_options[0]
                    )

                scenario_body = _render_section(
                    'INITIAL CONDITION',
                    hint='applied on reset',
                )
                with scenario_body:
                    scn_row = _render_field(scenario_body, 'Scenario', span=12)
                    with scn_row:
                        ui.select(
                            scenario_options,
                            value=current_scenario_label,
                            on_change=_on_scenario_change,
                        ).props(
                            'dense borderless popup-content-class="runtime-manager-mode-popup"'
                        ).classes('runtime-manager-page-input runtime-manager-page-select')
                    # Removed unit chip 'x₀' per user request

        # ── Status bar (DCS summary strip) ──
        with ui.element('div').classes('runtime-manager-statusbar'):
            with ui.element('div').classes('runtime-manager-statusbar-cell'):
                ui.label('STEP').classes('runtime-manager-statusbar-cell-label')
                tick_label = ui.label('—').classes(
                    'runtime-manager-statusbar-cell-value',
                )
            with ui.element('div').classes('runtime-manager-statusbar-cell'):
                ui.label('SIM TIME').classes('runtime-manager-statusbar-cell-label')
                sim_time_label = ui.label('—').classes(
                    'runtime-manager-statusbar-cell-value',
                )
            with ui.element('div').classes('runtime-manager-statusbar-cell'):
                ui.label('MODE').classes('runtime-manager-statusbar-cell-label')
                mode_summary = ui.label('—').classes('runtime-manager-statusbar-cell-value')

                def _sync_statusbar() -> None:
                    if is_dialog_open is not None and not is_dialog_open():
                        return

                    # Update Step
                    t_val = getattr(bridge.state, 'tick', None)
                    new_tick_text = f'{int(t_val) if t_val is not None else 0:>6d}'
                    if tick_label.text != new_tick_text:
                        tick_label.text = new_tick_text

                    # Update Sim Time
                    time_val = getattr(bridge.state, 'last_sim_time', None)
                    _time_val_f = float(time_val) if time_val is not None else 0.0
                    _converted = case_cfg.from_minutes(_time_val_f, case_default_unit)
                    new_time_text = f'{_converted:.2f} {case_default_unit}'
                    if sim_time_label.text != new_time_text:
                        sim_time_label.text = new_time_text

                    loop_order_val = getattr(case_cfg, 'LOOP_ORDER', None)
                    if not loop_order_val or len(loop_order_val) <= 1:
                        mode_summary.text = _mode_pill_label(bridge.state.controller_mode)
                        return

                    modes = []
                    for loop_id in loop_order_val:
                        current_mode = _normalize_mode_for_ui(
                            bridge,
                            bridge.state.loop_modes.get(
                                loop_id,
                                bridge.state.controller_mode or 'Automatic',
                            ),
                        ).upper()
                        modes.append(current_mode)

                    modes_set = set(modes)
                    if len(modes_set) == 1:
                        mode = modes.pop()
                        if mode == 'AUTOMATIC':
                            new_text = 'ALL AUTO'
                        elif mode == 'MANUAL':
                            new_text = 'ALL MAN'
                        elif mode == 'OFF':
                            new_text = 'ALL OFF'
                        else:
                            new_text = f'ALL {mode[:4]}'
                    else:
                        new_text = 'MIXED'

                    if mode_summary.text != new_text:
                        mode_summary.text = new_text

                ui.timer(0.25, _sync_statusbar)
            with ui.element('div').classes('runtime-manager-statusbar-cell'):
                ui.label('SCENARIO').classes('runtime-manager-statusbar-cell-label')
                # ``current_scenario_label`` is only assigned inside the
                # ``if scenario_order:`` branch above; fall back to the
                # em-dash placeholder for cases that have no scenario
                # list, and always hand ``ui.label`` a concrete ``str``
                # (its ``text`` parameter is typed as such).
                scenario_summary_text: str = (
                    current_scenario_label if (scenario_order and current_scenario_label) else '—'
                )
                scenario_summary = ui.label(
                    scenario_summary_text,
                ).classes('runtime-manager-statusbar-cell-value')
                if scenario_order:
                    _render_bind_text(
                        scenario_summary,
                        bridge.state,
                        'scenario',
                        backward=lambda value: scenario_labels_map.get(
                            str(value or '').strip().lower(),
                            str(value or '—').capitalize(),
                        ),
                    )

    # ── Wire the runtime handlers (after the DOM exists) ──
    def on_units_change(event: Any) -> None:
        selected_unit = str(
            _event_value(event, units_select.value) or units_select.value,
        )
        try:
            step_input.value = case_cfg.from_minutes(
                float(bridge.state.Ts),
                selected_unit,
            )
        except Exception:
            step_input.value = case_cfg.from_minutes(
                float(bridge.state.Ts),
                units_select.value,
            )

        raw_end = bridge.time_end_to_text()
        if raw_end is None or raw_end == '':
            end_input.value = ''
        else:
            try:
                end_input.value = f'{case_cfg.from_minutes(float(raw_end), selected_unit):g}'
            except Exception:
                end_input.value = raw_end

        try:
            bridge.state.global_sim_time = bridge.state.global_sim_time
        except Exception:
            pass

        # Re-render the unit chips and the live time readouts so the
        # user sees the new unit suffix on the End Time / Current
        # Time fields immediately.
        try:
            _hero_val = float(bridge.state.last_sim_time or 0.0)
            hero_current_time_label.text = f'{case_cfg.from_minutes(_hero_val, selected_unit):.4f}'
        except Exception:
            pass
        try:
            _st_val = float(bridge.state.last_sim_time or 0.0)
            sim_time_label.text = (
                f'{case_cfg.from_minutes(_st_val, selected_unit):.2f} {selected_unit}'
            )
        except Exception:
            pass

        # Hero unit suffix: also flip with the Units selector.
        try:
            hero_unit_label.text = selected_unit
        except Exception:
            pass

        record_info(f'Units changed to: {selected_unit}')

    # NiceGUI 3.x renamed ``Select.on_change`` → ``on_value_change``;
    # the lowercase ``on('change', …)`` event-name form is the most
    # version-stable binding and matches what the scenario select on
    # line 611 already uses via its ``on_change=`` constructor kwarg.
    try:
        units_select.on_value_change(on_units_change)
    except Exception:
        try:
            units_select.on('change', on_units_change)
        except Exception:
            pass

    def on_acceleration_change(event: Any) -> None:
        # Kept for backwards compatibility with anything that calls
        # ``on_acceleration_change`` programmatically (e.g. a future
        # unit test). The user's UI no longer fires this on every
        # change — see the ``blur`` / ``keydown.enter`` wiring
        # below — because we want the operator to confirm the
        # value (Enter or tab-out) before the engine is asked to
        # re-pace the simulation. This avoids the old behaviour
        # where every keystroke wrote into the bridge and
        # ``apply_runtime_configuration`` ran, causing the worker
        # to thrash when the user typed ``1`` on the way to
        # ``10`` (each digit was a separate "set acceleration to
        # 1" / "set acceleration to 10" event).
        current_value = _event_value(event, None)
        bridge.state.acceleration = (
            1.0 if current_value is None else max(float(current_value), 1e-12)
        )
        bridge.apply_runtime_configuration(restart_if_needed=False)
        record_info(f'Acceleration set to: {bridge.state.acceleration}')

    def _commit_step_input(
        _event: Any = None,
        element: Any = step_input,
    ) -> None:
        value = element.value
        if value is not None and not (isinstance(value, str) and not value.strip()):
            try:
                minutes = case_cfg.to_minutes(
                    float(value),
                    units_select.value,
                )
                bridge.state.Ts = max(float(minutes), 1e-12)
                try:
                    from app.hub.data_logger import write_audit_log

                    slug = getattr(bridge, 'case_name', 'unknown')
                    write_audit_log(
                        slug,
                        f'User changed Step Size to {value} {units_select.value}',
                        bridge=bridge,
                    )
                except Exception:
                    pass
            except Exception:
                pass
        bridge.apply_runtime_configuration(restart_if_needed=True)

    step_input.on('blur', _commit_step_input)
    step_input.on('keydown.enter', _commit_step_input)

    def _commit_end_input(
        _event: Any = None,
        element: Any = end_input,
    ) -> None:
        value = element.value
        if value is None or (isinstance(value, str) and not str(value).strip()):
            bridge.set_time_end_from_ui(value)
            try:
                from app.hub.data_logger import write_audit_log

                slug = getattr(bridge, 'case_name', 'unknown')
                write_audit_log(slug, f'User changed End Time to {value}', bridge=bridge)
            except Exception:
                pass
        else:
            try:
                minutes = case_cfg.to_minutes(
                    float(value),
                    units_select.value,
                )
                bridge.set_time_end_from_ui(minutes)
                try:
                    from app.hub.data_logger import write_audit_log

                    slug = getattr(bridge, 'case_name', 'unknown')
                    write_audit_log(
                        slug,
                        f'User changed End Time to {value} {units_select.value}',
                        bridge=bridge,
                    )
                except Exception:
                    pass
            except Exception:
                bridge.set_time_end_from_ui(value)
        bridge.apply_runtime_configuration(restart_if_needed=False)

        # End Time has been pushed into the bridge. Whether the
        # previous run finished naturally (``natural_stop=True``) or
        # not, we do NOT auto-resume — per user requirement: extending
        # End Time should never start the worker silently. The user
        # must press Continue (or Run) to actually advance.
        # ``set_run_button_disabled`` is driven by a 500 ms poll in
        # ``control_panel_page._build_pid_section`` and will lift the
        # block on the next tick now that ``time_end`` has moved past
        # the current sim time.
        #
        # We still re-sync the visible End Time field so the display
        # mirrors whatever ``bridge.set_time_end_from_ui`` accepted
        # (it normalises strings, infinities, etc.).
        try:
            raw_end = bridge.time_end_to_text()
            if raw_end is None or raw_end == '':
                end_input.value = ''
            else:
                try:
                    _end_conv = case_cfg.from_minutes(float(raw_end), units_select.value)
                    end_input.value = f'{_end_conv:g}'
                except Exception:
                    end_input.value = raw_end
        except Exception:
            logger.exception('Failed to re-sync end_input after time_end change')

    end_input.on('blur', _commit_end_input)
    end_input.on('keydown.enter', _commit_end_input)

    def _on_accel_commit(
        _event: Any = None,
        element: Any = accel_input,
    ) -> None:
        try:
            value = float(element.value) if element.value is not None else 1.0
        except (TypeError, ValueError):
            value = 1.0
        bridge.state.acceleration = max(value, 1e-12)
        bridge.apply_runtime_configuration(restart_if_needed=False)
        record_info(f'Acceleration set to: {bridge.state.acceleration}')
        try:
            from app.hub.data_logger import write_audit_log

            slug = getattr(bridge, 'case_name', 'unknown')
            write_audit_log(
                slug, f'User changed Acceleration to {bridge.state.acceleration}x', bridge=bridge
            )
        except Exception:
            pass

    accel_input.on('blur', _on_accel_commit)
    accel_input.on('keydown.enter', _on_accel_commit)

    # Live "Current Time" readout — bound to bridge.state.last_sim_time.
    # The big hero timer at the top of the card stays in sync with
    # whatever unit the user has selected in the Units dropdown.
    _render_bind_text(
        hero_current_time_label,
        bridge.state,
        'last_sim_time',
        backward=lambda value: (
            f'{case_cfg.from_minutes(float(value) if value is not None else 0.0, units_select.value):.4f}'  # noqa: E501
        ),
    )


__all__ = ['render_runtime_manager_body']
