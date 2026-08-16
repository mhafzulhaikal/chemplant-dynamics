# app/hub/perf_monitor.py

"""Reusable real-time stripchart for the Performance Monitoring section.

Moved from ``app/components/performance_monitor.py`` during the v1
purge — identical behaviour, new location. Consumes the same
``store.bridge`` ``_step_log`` deque; pages now obtain the store via
``hub.engine_control.bridge`` (any wrapper that exposes ``.bridge``
works).

This module mirrors the plot pattern in ``tests/main.py`` and the
selection pattern from the Data Logger:

- A NiceGUI ``ui.echart`` line chart, one trace per selected field,
  retuned to the DCS HMI palette (amber / cyan / green / red, amber
  axes, deep-black background).
- Smart y-axis: padded around the visible data range, rounded to a
  human-friendly step (1×/2×/5× decade).
- Scrolling x-axis: a fixed ``window_min`` window of simulation
  minutes.
- Flow-rate fields (FSP*, F_*, *.F) auto-scaled from per-second to
  per-hour for display.
- Periodic ``ui.timer`` flush that drains the bridge's step records
  into a bounded history deque and re-renders the chart.

Selection — single source of truth
----------------------------------
The Performance Monitoring page reads its plot selection from the
**same** state as the Data Logger:

- :pyattr:`bridge.state.selected_log_fields` — list of ``field``
  strings (``input:...`` / ``state:...`` / ``output:...``).
- :py:meth:`bridge.set_selected_log_fields` — setter that the
  Data Logger uses too.

The picker UI mirrors the Data Logger's *clickable header cell*
pattern: one cell per available field, in a horizontal-scrolling
row. Clicking a cell toggles the field in/out of the bridge's
selected set. Active cells get the green accent used by the Data
Logger; inactive cells are muted. Because both pages write to the
same bridge state, toggling a cell here is reflected instantly in
the Data Logger's log widget, and vice-versa.

Layout
------
Three stacked plot panels (input / state / output), in the visual
language of the right drawer. Each panel exposes the same header
cell row as the Data Logger (filtered to its own scope), followed
by a status strip ("Selected: …") and the echart stripchart.

Usage
-----

In a per-case page render function::

    from app.components.performance_monitor import render_performance_monitor

    def render_sthr_monitoring(store=None) -> None:
        render_performance_monitor(store, case_slug='sthr')

When ``store`` is ``None`` (engine not importable) the panel renders
a small placeholder explaining the situation, instead of crashing.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any

# pyrefly: ignore [missing-import]
from nicegui import ui

from app.ui.cell_labels import get_label, open_rename_dialog

_selected_perf_fields: dict[str, list[str]] = {}

__all__ = ['render_performance_monitor']


# ────────────────────────────────────────────────────────────────────────────
# Constants — mirror the test app
# ────────────────────────────────────────────────────────────────────────────

# Bounded history (steps).  The deque must be large enough to
# hold at least _DEFAULT_WINDOW_MIN minutes of data at the current
# Ts.  We compute the required length dynamically from the bridge's
# Ts and add a 20 % buffer so the chart never rolls off early.
# STHR  (Ts=0.01 min): 60/0.01 * 1.2 = 7 200
# Biodiesel (Ts≈0.00833 min): 60/0.00833 * 1.2 ≈ 8 640
_HISTORY_MAXLEN: int = 6000

# How often the flush timer runs (s) — 500 ms gives the UI plenty of
# breathing room while the chart still feels live.
_FLUSH_INTERVAL_S = 0.25

# Minimum interval between echart re-renders.
_CHART_THROTTLE_S = 0.25

# Default visible x-axis window (simulation minutes).
_DEFAULT_WINDOW_MIN = 60.0

# Section keys for the three stacked panels.
_PANEL_SECTIONS: tuple[tuple[str, str], ...] = (
    ('input', 'Input Section'),
    ('state', 'State Section'),
    ('output', 'Output Section'),
)

# Scope → display label (mirrors data_logger._SCOPE_TITLES).
_SCOPE_TITLES: dict[str, str] = {
    'input': 'INPUTS',
    'state': 'STATES',
    'output': 'OUTPUTS',
}

# Scope → hint (mirrors data_logger._SCOPE_HINTS).
_SCOPE_HINTS: dict[str, str] = {
    'input': 'Click a cell to plot / unplot the input signal',
    'state': 'Click a cell to plot / unplot the state signal',
    'output': 'Click a cell to plot / unplot the output signal',
}

# Trace palette for the chart — Curated High-Performance HMI (ISA-101)
# compliant palette. Avoids critical alarm red (#ff0000) and pure yellow
# (#ffff00), while providing high contrast and color-blind friendly distinction.
_DCS_TRACE_PALETTE: list[str] = [
    '#26c6da',  # 1.  Process Cyan (Primary PV)
    '#ff7043',  # 2.  Terracotta / Coral (Warm distinct)
    '#42a5f5',  # 3.  Azure Blue (Calm, high contrast)
    '#66bb6a',  # 4.  Sage Mint Green (Non-alarm green)
    '#9575cd',  # 5.  Soft Lavender / Purple
    '#e0a96d',  # 6.  Warm Sand / Ochre
    '#80deea',  # 7.  Ice Teal
    '#f06292',  # 8.  Dusty Rose
    '#4db6ac',  # 9.  Seafoam Slate
    '#7986cb',  # 10. Periwinkle Blue
    '#dce775',  # 11. Soft Khaki Gold
    '#ffab91',  # 12. Peach Amber
    '#0097a7',  # 13. Deep Slate Teal
    '#ba68c8',  # 14. Muted Lilac
    '#aed581',  # 15. Pistachio Green
    '#cfd8dc',  # 16. Platinum Silver
]


def _color_for_index(index: int) -> str:
    """Return the palette color for the ``index``-th selected field.

    The picker cells and the chart both use this resolver so the cell's
    accent border matches the trace it produces.
    """
    return _DCS_TRACE_PALETTE[index % len(_DCS_TRACE_PALETTE)]


def _repaint_cell_dot(cell: Any, color: str) -> None:
    """Update (or clear) the color-dot child of a picker cell.

    The cell is a NiceGUI ``ui.element('div')``. Its first child is a
    ``span.pm-cell-color-dot`` we inject when building the grid. The
    dot's color is set via inline ``style`` so it can be re-tinted as
    the active-field order changes without rebuilding the cell from
    scratch.
    """
    try:
        dot = next(
            (
                child
                for child in cell.default_slot.children
                if 'pm-cell-color-dot' in getattr(child, '_classes', [])
            ),
            None,
        )
    except Exception:
        return

    if dot is None:
        return

    if color:
        dot.props(
            f'style="background-color: {color}; box-shadow: none; "',
        )
    else:
        # Show as a muted white dot when inactive
        dot.props(
            'style="background-color: #ffffff; opacity: 0.3; box-shadow: none; "',
        )


# ────────────────────────────────────────────────────────────────────────────
# Helpers — copied from tests/main.py with minor cleanup
# ────────────────────────────────────────────────────────────────────────────


def _extract_plot_value(step_entry: dict, field_name: str, registry: Any) -> float | None:
    """Pull the value for ``field_name`` out of one history entry."""
    scope, _, tag = field_name.partition(':')

    if scope == 'input':
        value = step_entry.get('inputs', {}).get(tag)
    elif scope == 'state':
        value = step_entry.get('states', {}).get(tag)
    elif scope == 'output':
        value = step_entry.get('outputs', {}).get(tag)
    elif scope == 'meta' and tag == 'time':
        value = step_entry.get('time_min')
    elif scope == 'meta' and tag == 'step':
        value = step_entry.get('step_index')
    else:
        value = None

    if value is None:
        return None
    try:
        value = float(value)
    except TypeError, ValueError:
        return value

    return value * registry.get_scale_for(field_name)


def _split_fields_by_scope(fields: list[str]) -> dict[str, list[str]]:
    """Bucket ``input:…/state:…/output:…/meta:…`` fields by scope.

    ``meta:`` fields are folded into ``state`` so the three scope cards
    cover every available signal without a fourth card. Mirrors
    ``data_logger._split_fields_by_scope``.
    """
    buckets: dict[str, list[str]] = {scope: [] for scope, _ in _PANEL_SECTIONS}
    for field in fields:
        scope, _, _ = field.partition(':')
        if scope in buckets:
            buckets[scope].append(field)
        elif scope == 'meta':
            buckets['state'].append(field)
    return buckets


def _smart_yaxis_config(series: list[dict]) -> dict:
    """Y-axis config with padding around the visible data range.

    The min/max are pulled in to ``floor(low/step)*step`` /
    ``ceil(high/step)*step`` so the gridlines land on round numbers.
    """
    yaxis_config: dict[str, Any] = {
        'type': 'value',
        'scale': True,
        'axisLine': {'lineStyle': {'color': '#ffd54f'}},
        'axisLabel': {
            'color': '#ffd54f',
            'fontFamily': 'JetBrains Mono, monospace',
            'fontSize': 10,
            ':formatter': (
                'v => (v !== 0 && Math.abs(v) < 0.01) ? v.toExponential(2) : v.toFixed(2)'
            ),
        },
        'splitLine': {
            'lineStyle': {'color': 'rgba(255, 213, 79, 0.10)'},
        },
    }

    all_y: list[float] = []
    for item in series:
        for point in item.get('data', []):
            if point and len(point) >= 2:
                try:
                    all_y.append(float(point[1]))
                except TypeError, ValueError:
                    pass

    if not all_y:
        return yaxis_config

    y_min = min(all_y)
    y_max = max(all_y)
    y_range = y_max - y_min

    if y_range > 0:
        padding = y_range * 0.3
        low = y_min - padding
        high = y_max + padding
    else:
        padding = 0.005
        low = y_min - padding
        high = y_max + padding

    span = high - low if high != low else abs(high) if high != 0 else 1.0
    magnitude = 10 ** math.floor(math.log10(span))
    step = magnitude / 2

    yaxis_config['min'] = math.floor(low / step) * step
    yaxis_config['max'] = math.ceil(high / step) * step

    return yaxis_config


def _save_chart_as(chart: Any, fmt: str, filename_prefix: str | None = None) -> None:
    """Trigger high-resolution download of the specified chart in PNG or JPEG format."""
    from datetime import datetime

    from nicegui import ui

    if chart is None:
        ui.notify('Chart is not ready to export', color='warning')
        return

    # Extract target ID / class
    chart_id = getattr(chart, 'id', None)
    target_classes = getattr(chart, '_classes', ['pm-panel-chart'])
    specific_class = next(
        (c for c in target_classes if c.startswith('pm-chart-')),
        target_classes[0] if target_classes else 'pm-panel-chart',
    )

    timestamp = datetime.now().strftime('%Y-%m-%dT%H%M%S')
    file_prefix = filename_prefix or 'performance_plot'
    filename = f'{file_prefix}_{timestamp}.{fmt}'

    js = f"""
    (() => {{
        try {{
            // 1. Locate the container element
            let container = document.querySelector('.{specific_class}') ||
                            document.getElementById('{specific_class}') ||
                            document.getElementById('c{chart_id}') ||
                            document.getElementById('{chart_id}');
            if (!container && typeof getElement === 'function') {{
                const w = getElement({chart_id});
                if (w && w.$el) container = w.$el;
            }}
            if (!container) {{
                container = document.querySelector('.nicegui-echart');
            }}
            if (!container) {{
                console.error('Chart container not found');
                return false;
            }}

            // 2. Locate the canvas element
            let canvas = container.querySelector('canvas');
            if (!canvas) {{
                const canvases = container.getElementsByTagName('canvas');
                if (canvases.length > 0) canvas = canvases[0];
            }}
            if (!canvas) {{
                console.error('Canvas element not found in chart container');
                return false;
            }}

            // 3. Prepare export canvas with black background
            const bgCanvas = document.createElement('canvas');
            bgCanvas.width = canvas.width;
            bgCanvas.height = canvas.height;
            const ctx = bgCanvas.getContext('2d');
            ctx.fillStyle = '#000000';
            ctx.fillRect(0, 0, bgCanvas.width, bgCanvas.height);
            ctx.drawImage(canvas, 0, 0);

            // 4. Generate download link directly in browser
            const mimeType = ('{fmt}' === 'jpeg' || '{fmt}' === 'jpg') ? 'image/jpeg' : 'image/png';
            const dataUrl = bgCanvas.toDataURL(mimeType, 0.95);
            const a = document.createElement('a');
            a.download = '{filename}';
            a.href = dataUrl;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            return true;
        }} catch (e) {{
            console.error('Export failed:', e);
            return false;
        }}
    }})();
    """
    ui.run_javascript(js)
    ui.notify(f'Saving {filename}...', color='blue-grey-8', icon='download')


# ────────────────────────────────────────────────────────────────────────────
# Main entry point
# ────────────────────────────────────────────────────────────────────────────


def render_performance_monitor(
    store: Any | None,
    *,
    case_slug: str,
    window_min: float = _DEFAULT_WINDOW_MIN,
    popout_url: str | None = None,
) -> None:
    """Render the Performance Monitoring page.

    The page contains three stacked plot panels (input / state /
    output), each in a card styled like the right drawer. The plot
    selection is the same source of truth as the Data Logger:
    ``bridge.state.selected_log_fields`` — toggling a cell here
    toggles the column in the Data Logger's log widget too.

    Parameters
    ----------
    store:
        A ``BaseBridgeStore`` (or subclass) bound to a running
        :class:`GenericBridge`. ``None`` triggers the placeholder.
    case_slug:
        Reserved for future per-case hookups (loop grouping, etc.).
        The current implementation does not consume it, but it is
        kept for API compatibility with the original component.
    window_min:
        Width of the scrolling x-axis window in simulation minutes.
    popout_url:
        Optional URL for the pop-out button.
    """
    _ = case_slug  # kept for API compatibility

    if store is None or getattr(store, 'bridge', None) is None:
        with ui.column().classes('pm-page w-full gap-3'):
            with ui.row().classes('pm-page-header w-full items-center justify-between flex-nowrap'):
                with ui.column().classes('gap-1'):
                    ui.label('Performance Monitoring').classes('pm-page-title')
                    ui.label('Engine not connected').classes('pm-page-subtitle')
            ui.separator().classes('pm-separator')
            ui.label(
                'Performance monitoring is not available without an engine '
                'connection. Start the engine and reload this page.',
            ).classes('text-white/70 text-sm')
        return

    bridge = store.bridge
    state = PerfMonitorState(store, bridge, case_slug, window_min)

    with ui.column().classes('pm-page w-full gap-3'):
        # ── Page header — matches the right-drawer title language ──
        with ui.row().classes('pm-page-header w-full items-center justify-between flex-nowrap'):
            with ui.column().classes('gap-1'):
                ui.label('Performance Monitoring').classes('pm-page-title')
                ui.label(
                    f'Live signals · {window_min:g} min window · click cells to toggle',
                ).classes('pm-page-subtitle')

            with ui.row().classes('items-center gap-2'):
                ui.button(
                    'All inputs',
                    on_click=lambda: state.toggle_all_for_scope('input'),
                    color=None,
                ).props('flat no-caps dense').classes('pm-action-btn')
                ui.button(
                    'All states',
                    on_click=lambda: state.toggle_all_for_scope('state'),
                    color=None,
                ).props('flat no-caps dense').classes('pm-action-btn')
                ui.button(
                    'All outputs',
                    on_click=lambda: state.toggle_all_for_scope('output'),
                    color=None,
                ).props('flat no-caps dense').classes('pm-action-btn')
                ui.button('Clear plots', on_click=state.clear_all, color=None).props(
                    'flat no-caps dense'
                ).classes('pm-action-btn pm-action-btn-danger')

                with (
                    ui.button('Save', color=None)
                    .props('flat no-caps dense icon-right=expand_more')
                    .classes('pm-action-btn pm-save-btn')
                ):
                    with ui.menu().classes('pm-save-menu'):
                        ui.menu_item(
                            'Input Section  →  PNG',
                            lambda: _save_chart_as(
                                state.charts.get('input'),
                                'png',
                                'performance_input',
                            ),
                        )
                        ui.menu_item(
                            'Input Section  →  JPEG',
                            lambda: _save_chart_as(
                                state.charts.get('input'),
                                'jpeg',
                                'performance_input',
                            ),
                        )
                        ui.separator()
                        ui.menu_item(
                            'State Section  →  PNG',
                            lambda: _save_chart_as(
                                state.charts.get('state'),
                                'png',
                                'performance_state',
                            ),
                        )
                        ui.menu_item(
                            'State Section  →  JPEG',
                            lambda: _save_chart_as(
                                state.charts.get('state'),
                                'jpeg',
                                'performance_state',
                            ),
                        )
                        ui.separator()
                        ui.menu_item(
                            'Output Section  →  PNG',
                            lambda: _save_chart_as(
                                state.charts.get('output'),
                                'png',
                                'performance_output',
                            ),
                        )
                        ui.menu_item(
                            'Output Section  →  JPEG',
                            lambda: _save_chart_as(
                                state.charts.get('output'),
                                'jpeg',
                                'performance_output',
                            ),
                        )

                if popout_url:
                    from app.components.popout_button import (
                        render_popout_button,
                    )

                    render_popout_button(popout_url, classes='pm-action-btn')

        ui.separator().classes('pm-separator')

        _mount_stripchart(
            hub=store,
            bridge=bridge,
            case_slug=case_slug,
            window_min=window_min,
            state=state,
        )


class PerfMonitorState:
    """Shared state for Performance Monitor (both stacked and unified
    layouts)."""

    def __init__(
        self,
        hub: Any,
        bridge: Any,
        case_slug: str,
        window_min: float,
        is_independent: bool = False,
        popout_id: str | None = None,
    ):
        from collections import deque

        self.hub = hub
        self.bridge = bridge
        self.case_slug = case_slug
        self.window_min = window_min
        self.is_independent = is_independent
        self.popout_id = popout_id
        self.storage_key = (
            f'pm_selected_{self.case_slug}_{self.popout_id}'
            if (self.is_independent and self.popout_id)
            else f'pm_selected_{self.case_slug}'
        )

        _ts = float(getattr(self.bridge.state, 'Ts', 0.01) or 0.01)
        _ts = max(_ts, 1e-12)
        self.history_maxlen = max(_HISTORY_MAXLEN, int(1.2 * _DEFAULT_WINDOW_MIN / _ts))

        self.step_history = deque(maxlen=self.history_maxlen)
        self.watermark = [-1]

        self.last_seen_reset_counter = [getattr(self.hub, '_reset_counter', 0)]
        self.available_fields = list(getattr(self.bridge.state, 'available_log_fields', []) or [])
        self.fields_by_scope = _split_fields_by_scope(self.available_fields)
        self.last_render_time = [0.0]

        self.on_refresh_cells = []
        self.on_refresh_status = []
        self.on_update_charts = []
        self.on_rebuild_panels = []
        self.charts = {}

        from nicegui import app

        if not hasattr(self.hub, 'pm_selected_fields_map'):
            self.hub.pm_selected_fields_map = {}

        self.session_key = self.popout_id if (self.is_independent and self.popout_id) else 'main'

        try:
            saved = app.storage.user.get(self.storage_key)
            if saved is not None:
                self.hub.pm_selected_fields_map[self.session_key] = list(saved)
            else:
                self.hub.pm_selected_fields_map[self.session_key] = list(
                    self.hub.pm_selected_fields_map.get(self.session_key, [])
                )
        except Exception:
            self.hub.pm_selected_fields_map[self.session_key] = list(
                self.hub.pm_selected_fields_map.get(self.session_key, [])
            )

        if hasattr(self.hub, 'update_bridge_selected_fields'):
            self.hub.update_bridge_selected_fields()

    def commit_selection(self, new_fields: list[str]) -> None:
        available = list(getattr(self.bridge.state, 'available_log_fields', []) or [])
        ordered = [field for field in available if field in set(new_fields)]
        if not hasattr(self.hub, 'pm_selected_fields_map'):
            self.hub.pm_selected_fields_map = {}
        self.hub.pm_selected_fields_map[self.session_key] = ordered
        try:
            from nicegui import app

            app.storage.user[self.storage_key] = ordered
        except Exception:
            pass
        if hasattr(self.hub, 'update_bridge_selected_fields'):
            self.hub.update_bridge_selected_fields()

    def all_selected(self) -> list[str]:
        if not hasattr(self.hub, 'pm_selected_fields_map'):
            self.hub.pm_selected_fields_map = {}
        return list(self.hub.pm_selected_fields_map.get(self.session_key, []))

    def selected_for_scope(self, scope: str) -> list[str]:
        current = self.all_selected()
        return [
            field
            for field in current
            if field.partition(':')[0] == scope or (scope == 'state' and field.startswith('meta:'))
        ]

    def toggle_field(self, scope: str, field_name: str) -> None:
        current = list(self.all_selected())

        if field_name in current:
            current = [f for f in current if f != field_name]
            try:
                from app.hub.data_logger import write_audit_log

                write_audit_log(
                    self.case_slug,
                    f"Deselected '{field_name}' for plotting",
                    bridge=self.bridge,
                )
            except Exception:
                pass
        else:
            current.append(field_name)
            try:
                from app.hub.data_logger import write_audit_log

                write_audit_log(
                    self.case_slug,
                    f"Selected '{field_name}' for plotting",
                    bridge=self.bridge,
                )
            except Exception:
                pass

        self.commit_selection(current)
        for cb in self.on_refresh_cells:
            cb(None)
        for cb in self.on_refresh_status:
            cb(None)
        for cb in self.on_update_charts:
            cb(None)

    def toggle_all_for_scope(self, scope: str) -> None:
        try:
            available_for_scope = [
                field
                for field in getattr(self.bridge.state, 'available_log_fields', [])
                if field.partition(':')[0] == scope
                or (scope == 'state' and field.startswith('meta:'))
            ]
            if not available_for_scope:
                return
            current = self.all_selected()
            current_set = set(current)
            available_set = set(available_for_scope)

            all_selected = all(f in current_set for f in available_for_scope)
            if all_selected:
                new_selection = [f for f in current if f not in available_set]
                from app.hub.data_logger import write_audit_log

                write_audit_log(
                    self.case_slug,
                    f'Deselected All {scope.title()}s for plotting',
                    bridge=self.bridge,
                )
            else:
                new_selection = current + [f for f in available_for_scope if f not in current_set]
                from app.hub.data_logger import write_audit_log

                write_audit_log(
                    self.case_slug,
                    f'Selected All {scope.title()}s for plotting',
                    bridge=self.bridge,
                )

            self.commit_selection(new_selection)
        except Exception:
            pass
        for cb in self.on_refresh_cells:
            cb(None)
        for cb in self.on_refresh_status:
            cb(None)
        for cb in self.on_update_charts:
            cb(None)

    def clear_all(self) -> None:
        try:
            self.commit_selection([])
            from app.hub.data_logger import write_audit_log

            write_audit_log(
                self.case_slug,
                'Cleared all fields for plotting',
                bridge=self.bridge,
            )
        except Exception:
            pass
        for cb in self.on_refresh_cells:
            cb(None)
        for cb in self.on_refresh_status:
            cb(None)
        for cb in self.on_update_charts:
            cb(None)
        from nicegui import ui

        ui.notify('Plot selections cleared', color='blue-grey-8', icon='check_circle_outline')

    def start_flush_timer(self) -> None:
        def _flush():
            current_reset_counter = getattr(self.hub, '_reset_counter', 0)

            if current_reset_counter > self.last_seen_reset_counter[0]:
                self.step_history.clear()
                self.watermark[0] = -1
                for cb in self.on_update_charts:
                    cb(None)
                self.last_seen_reset_counter[0] = current_reset_counter

            current_available = list(getattr(self.bridge.state, 'available_log_fields', []) or [])
            if current_available != self.available_fields:
                self.available_fields = current_available
                self.fields_by_scope.clear()
                self.fields_by_scope.update(_split_fields_by_scope(current_available))
                for cb in self.on_rebuild_panels:
                    cb()
                for cb in self.on_refresh_cells:
                    cb(None)
                for cb in self.on_update_charts:
                    cb(None)

            chart_has_new_data = False
            try:
                new_steps = self.hub.get_history_since(self.watermark[0])
            except Exception:
                new_steps = []

            for entry in new_steps:
                if not isinstance(entry, dict):
                    continue
                step_index = entry.get('step_index')
                if step_index is None or step_index <= self.watermark[0]:
                    continue
                self.watermark[0] = int(step_index)
                self.step_history.append(dict(entry))
                chart_has_new_data = True

            if chart_has_new_data:
                now = time.perf_counter()
                if now - self.last_render_time[0] >= _CHART_THROTTLE_S:
                    for cb in self.on_update_charts:
                        cb(None)
                    self.last_render_time[0] = now

        ui.timer(_FLUSH_INTERVAL_S, _flush)


def _mount_stripchart(
    *,
    hub: Any,
    bridge: Any,  # noqa: ARG001  reserved for future per-bridge filtering
    case_slug: str,  # noqa: ARG001  reserved for future slug-scoped display
    window_min: float,  # noqa: ARG001  consumed via state.window_min
    state: PerfMonitorState,
) -> None:
    panel_containers: dict[str, Any] = {}
    for section, _title in _PANEL_SECTIONS:
        with ui.card().classes('pm-panel w-full') as panel:
            pass
        panel_containers[section] = panel

    status_els: dict[str, Any] = {}
    cell_refs: dict[str, dict[str, Any]] = {scope: {} for scope, _ in _PANEL_SECTIONS}

    def _refresh_cells(scope: str | None) -> None:
        scopes_to_update = [scope] if scope else [s for s, _ in _PANEL_SECTIONS]
        all_active = state.all_selected()
        for s in scopes_to_update:
            active_in_order = state.selected_for_scope(s)
            color_by_field: dict[str, str] = {
                field_name: hub.get_field_color(field_name, all_active)
                for field_name in active_in_order
            }
            active = set(active_in_order)
            for field_name, cell in cell_refs.get(s, {}).items():
                if cell is None:
                    continue
                try:
                    if field_name in active:
                        cell.classes(add='pm-cell-active', remove='pm-cell-inactive')
                        cell_color = color_by_field.get(field_name, '')
                        if cell_color:
                            cell.props(
                                f'style="border: 1px solid {cell_color} '
                                f'!important; '
                                f'background-color: {cell_color}26 '
                                f'!important; '
                                f'box-shadow: none; "'
                            )
                        _repaint_cell_dot(cell, cell_color)
                    else:
                        cell.classes(add='pm-cell-inactive', remove='pm-cell-active')
                        cell.props('style=""')
                        _repaint_cell_dot(cell, '')
                except Exception:
                    pass

    def _on_pm_cell_renamed(field_name: str, cell: Any) -> None:
        _, _, tag = field_name.partition(':')
        new_display = get_label(field_name, tag.upper())
        try:
            for child in cell.default_slot.children:
                inner = getattr(child, 'default_slot', None)
                if inner is None:
                    continue
                for grandchild in inner.children:
                    if 'pm-cell-tag' in getattr(grandchild, '_classes', []):
                        grandchild.set_text(new_display)
                        return
        except Exception:
            pass

    def _refresh_status(scope: str | None) -> None:
        scopes_to_update = [scope] if scope else [s for s, _ in _PANEL_SECTIONS]
        all_active = state.all_selected()
        for s in scopes_to_update:
            el = status_els.get(s)
            if el is None:
                continue
            fields = state.selected_for_scope(s)
            try:
                el.clear()
                with el:
                    if fields:
                        active_in_order = state.selected_for_scope(s)
                        color_by_field = {
                            f: hub.get_field_color(f, all_active) for f in active_in_order
                        }
                        for i, f in enumerate(fields):
                            if i > 0:
                                ui.label('·').classes('pm-panel-statusbar-value text-white/30 px-2')
                            c = color_by_field.get(f, '#ffffff')
                            ui.label(_format_legend_label(f)).classes(
                                'pm-panel-statusbar-value font-mono tracking-tight font-bold'
                            ).style(f'color: {c} !important;')
                    else:
                        ui.label('(no signal selected)').classes(
                            'pm-panel-statusbar-value pm-panel-statusbar-value-empty'
                        )
            except Exception:
                pass

    def _update_panel_chart(scope: str | None) -> None:
        scopes_to_update = [scope] if scope else [s for s, _ in _PANEL_SECTIONS]
        all_active = state.all_selected()
        for s in scopes_to_update:
            chart = state.charts.get(s)
            if chart is None:
                continue
            _update_chart(
                chart=chart,
                selected_fields=state.selected_for_scope(s),
                step_history=state.step_history,
                window_min=state.window_min,
                registry=state.hub.registry,
                all_selected_fields=all_active,
                hub=hub,
            )

    def _build_panel(scope: str, title: str) -> None:
        scope_fields = state.fields_by_scope.get(scope, [])

        with ui.row().classes('pm-panel-header w-full items-center justify-between flex-nowrap'):
            with ui.column().classes('pm-panel-title-group'):
                ui.label(title).classes('pm-panel-title')
                ui.label(_SCOPE_HINTS[scope]).classes('pm-panel-hint')
            with (
                ui.button(icon='save', color=None)
                .props('flat dense round size=sm')
                .classes('pm-action-btn pm-save-btn')
            ):
                with ui.menu().classes('pm-save-menu'):
                    ui.menu_item(
                        f'{title}  →  PNG',
                        lambda _, s=scope: _save_chart_as(
                            state.charts.get(s), 'png', f'performance_{s}'
                        ),
                    )
                    ui.menu_item(
                        f'{title}  →  JPEG',
                        lambda _, s=scope: _save_chart_as(
                            state.charts.get(s), 'jpeg', f'performance_{s}'
                        ),
                    )

        ui.separator().classes('pm-panel-separator')

        with ui.column().classes('pm-panel-body w-full'):
            cell_container = ui.element('div').classes('pm-panel-cell-container')
            with cell_container:
                _build_header_grid(scope, scope_fields)

            with ui.row().classes('pm-panel-statusbar w-full items-center'):
                ui.label('Selected').classes('pm-panel-statusbar-label')
                status_els[scope] = ui.row().classes(
                    'items-center gap-0 flex-1 min-w-0 overflow-hidden'
                )

            _refresh_status(scope)

            chart = _build_chart(chart_id=f'pm-chart-{scope}')
            state.charts[scope] = chart
            _update_panel_chart(scope)

    def _build_header_grid(scope: str, scope_fields: list[str]) -> None:
        if not scope_fields:
            ui.label('(no fields available for this scope)').classes('pm-panel-cell-empty')
            return

        with ui.row().classes('pm-panel-cell-grid'):
            active_in_order = state.selected_for_scope(scope)
            all_active = state.all_selected()
            color_by_field: dict[str, str] = {
                field_name: hub.get_field_color(field_name, all_active)
                for field_name in active_in_order
            }
            active = set(active_in_order)

            for field_name in scope_fields:
                scope_prefix, _, tag = field_name.partition(':')
                is_active = field_name in active
                cell_color = color_by_field.get(field_name, '')
                display_tag = get_label(field_name, tag.upper())

                cell = ui.element('div').classes(
                    'pm-cell ' + ('pm-cell-active' if is_active else 'pm-cell-inactive')
                )
                if is_active and cell_color:
                    cell.props(
                        f'style="border: 1px solid {cell_color} '
                        f'!important; '
                        f'background-color: {cell_color}26 '
                        f'!important; '
                        f'box-shadow: none; "'
                    )
                with cell:
                    dot = ui.element('span').classes('pm-cell-color-dot')
                    if is_active and cell_color:
                        dot.props(f'style="background-color: {cell_color}; box-shadow: none; "')
                    else:
                        dot.props(
                            'style="background-color: #ffffff; opacity: 0.3; box-shadow: none; "'
                        )
                    with ui.column().classes('pm-cell-text'):
                        ui.label(display_tag).classes('pm-cell-tag')
                        ui.label(scope_prefix.upper()).classes('pm-cell-meta')

                cell.on(
                    'click.stop',
                    lambda _event, s=scope, f=field_name: state.toggle_field(s, f),
                )

                def _make_pm_dblclick(fn=field_name, c=cell):
                    def _handler(_event):
                        open_rename_dialog(
                            fn,
                            get_label(fn, fn.partition(':')[2].upper()),
                            on_confirm=lambda: _on_pm_cell_renamed(fn, c),
                        )

                    return _handler

                cell.on('dblclick', _make_pm_dblclick())
                cell_refs[scope][field_name] = cell

    def _rebuild_panels():
        for scope, title in _PANEL_SECTIONS:
            cell_refs[scope].clear()
            panel = panel_containers[scope]
            panel.clear()
            with panel:
                _build_panel(scope, title)

    state.on_refresh_cells.append(_refresh_cells)
    state.on_refresh_status.append(_refresh_status)
    state.on_update_charts.append(_update_panel_chart)
    state.on_rebuild_panels.append(_rebuild_panels)

    for scope, title in _PANEL_SECTIONS:
        with panel_containers[scope]:
            _build_panel(scope, title)
        _refresh_cells(scope)

    ui.element('div').classes('min-h-[0.5rem] w-full flex-shrink-0')
    state.start_flush_timer()


def _build_chart(unified: bool = False, chart_id: str | None = None) -> Any:
    """Build a blank echart with the DCS HMI palette."""
    axis_formatter = 'v => (v !== 0 && Math.abs(v) < 0.01) ? v.toExponential(2) : v.toFixed(2)'
    tooltip_formatter = (
        'params => { '
        'const fmt = v => (v !== 0 && Math.abs(v) < 0.01) '
        '? v.toExponential(2) '
        ': v.toFixed(2); '
        'let s = "t: " + fmt(params[0].axisValue) + "<br/>"; '
        'params.forEach(p => { '
        's += p.marker + p.seriesName + ": " + fmt(p.value[1]) + "<br/>"; '
        '}); '
        'return s; '
        '}'
    )

    chart = ui.echart(
        {
            'animation': False,
            'backgroundColor': '#000000',
            'color': _DCS_TRACE_PALETTE,
            'tooltip': {
                'trigger': 'axis',
                'backgroundColor': 'rgba(17, 17, 17, 0.95)',
                'borderColor': '#ffd54f',
                'borderWidth': 1,
                'textStyle': {
                    'color': '#ffffff',
                    'fontFamily': 'JetBrains Mono, monospace',
                    'fontSize': 11,
                },
                'axisPointer': {
                    'type': 'line',
                    'lineStyle': {
                        'color': '#ffd54f',
                        'width': 1,
                        'type': 'dashed',
                        'opacity': 0.7,
                    },
                },
                ':formatter': tooltip_formatter,
            },
            'toolbox': {
                'show': False,
                'feature': {
                    'saveAsImage': {
                        'show': True,
                        'title': 'Save',
                        'backgroundColor': '#000000',
                        'pixelRatio': 2,
                    },
                },
                'iconStyle': {'borderColor': '#ffd54f'},
                'right': '3%',
                'top': '1%',
            },
            # Legend intentionally disabled — the picker cell row above
            # the chart IS the legend. Each active cell carries the
            # trace color end-to-end (border, tinted background, color
            # dot) so the operator can read the cell ↔ line mapping
            # directly without a separate legend strip eating into the
            # chart well.
            'legend': {'show': False},
            'grid': {
                'left': '4%',
                'right': '3%',
                # Legend removed → top margin can be tightened so the
                # chart well fills the freed vertical space.
                'top': '6%',
                'bottom': 25,
                'containLabel': True,
                'borderColor': 'rgba(255, 213, 79, 0.25)',
                'show': True,
            },
            'xAxis': {
                'type': 'value',
                # No axis title — the picker row above the chart is
                # the "label" for each trace. The X axis still shows
                # tick numbers (sim_min) without a heading.
                'name': '',
                'nameTextStyle': {'show': False},
                'axisLine': {'lineStyle': {'color': '#ffd54f'}},
                'axisTick': {'lineStyle': {'color': '#ffd54f'}},
                'axisLabel': {
                    'color': '#ffd54f',
                    'fontFamily': 'JetBrains Mono, monospace',
                    'fontSize': 10,
                    ':formatter': axis_formatter,
                },
                'splitLine': {
                    'lineStyle': {
                        'color': 'rgba(255, 213, 79, 0.08)',
                        'type': 'dashed',
                    },
                },
            },
            'yAxis': {
                'type': 'value',
                'name': '',
                'nameTextStyle': {'show': False},
                'scale': True,
                'min': 'dataMin',
                'max': 'dataMax',
                'axisLine': {'lineStyle': {'color': '#ffd54f'}},
                'axisTick': {'lineStyle': {'color': '#ffd54f'}},
                'axisLabel': {
                    'color': '#ffd54f',
                    'fontFamily': 'JetBrains Mono, monospace',
                    'fontSize': 10,
                    ':formatter': axis_formatter,
                },
                'splitLine': {
                    'lineStyle': {
                        'color': 'rgba(255, 213, 79, 0.10)',
                        'type': 'dashed',
                    },
                },
            },
            'series': [],
        },
    )

    if unified:
        chart.classes('absolute inset-0 w-full h-full m-0')
        chart.style('height: 100% !important; min-height: 0 !important;')
    else:
        chart.classes('pm-panel-chart')

    if chart_id:
        chart.props(f'id="{chart_id}"')
        chart.classes(chart_id)

    return chart


def _format_legend_label(field_name: str) -> str:
    """Render ``field_name`` as an uppercase HMI legend tag.

    ``input:FSP-100.SP`` → ``FSP-100.SP  ·  INPUT``. The tag (top half)
    is the part the operator recognises; the scope (bottom half) is the
    section it lives in, matching the cell picker layout.
    """
    scope, _, tag = field_name.partition(':')
    display = get_label(field_name, tag.upper())
    return f'{display}  ·  {scope.upper()}'


def _downsample_points(points: list[list[float]], max_points: int = 500) -> list[list[float]]:
    """Downsample a series of [time, val] points using Min-Max bucketing.

    Preserves peaks, valleys, and endpoints while keeping the payload
    ultra-light.
    """
    n = len(points)
    if n <= max_points:
        return points

    num_buckets = max_points // 2
    if num_buckets < 1:
        return points

    bucket_size = n / num_buckets
    result: list[list[float]] = [points[0]]

    for i in range(num_buckets):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        chunk = points[start:end]
        if not chunk:
            continue
        min_pt = min(chunk, key=lambda p: p[1])
        max_pt = max(chunk, key=lambda p: p[1])
        if min_pt[0] <= max_pt[0]:
            if min_pt != result[-1]:
                result.append(min_pt)
            if max_pt != result[-1]:
                result.append(max_pt)
        else:
            if max_pt != result[-1]:
                result.append(max_pt)
            if min_pt != result[-1]:
                result.append(min_pt)

    if points[-1] != result[-1]:
        result.append(points[-1])
    return result


def _update_chart(
    *,
    chart: Any,
    selected_fields: list[str],
    step_history: deque,
    window_min: float,
    registry: Any,
    all_selected_fields: list[str] | None = None,
    hub: Any = None,
) -> None:
    """Push the latest series into ``chart`` from the history deque.

    ``selected_fields`` is the scope-filtered slice of the bridge's
    ``selected_log_fields`` (one entry per field the user wants
    plotted). Each field becomes one trace on the chart; the trace color
    is the same :func:`_color_for_index` index the picker cell uses, so
    the cell border and the line on the chart are guaranteed to match.
    """
    series: list[dict[str, Any]] = []
    legend_names: list[str] = []

    for index, field_name in enumerate(selected_fields):
        points: list[list[float]] = []
        for step_entry in step_history:
            x_value = step_entry.get('time_min')
            y_value = _extract_plot_value(step_entry, field_name, registry)
            if x_value is None or y_value is None:
                continue
            try:
                points.append([float(x_value), float(y_value)])
            except TypeError, ValueError:
                continue

        points = _downsample_points(points, max_points=500)

        if hub is not None:
            color = hub.get_field_color(field_name, all_selected_fields or selected_fields)
        else:
            color_index = (
                all_selected_fields.index(field_name)
                if (all_selected_fields is not None and field_name in all_selected_fields)
                else index
            )
            color = _color_for_index(color_index)
        series.append(
            {
                'name': _format_legend_label(field_name),
                'type': 'line',
                'showSymbol': False,
                'connectNulls': True,
                'smooth': False,
                'lineStyle': {'width': 2, 'color': color},
                'itemStyle': {'color': color},
                'data': points,
            },
        )
        legend_names.append(_format_legend_label(field_name))

    chart.options['series'] = series
    chart.options['yAxis'] = _smart_yaxis_config(series)
    chart.options.setdefault('xAxis', {})

    try:
        data_max: float | None = None
        if step_history and step_history[-1].get('time_min') is not None:
            try:
                data_max = float(step_history[-1]['time_min'])
            except TypeError, ValueError:
                pass

        if data_max is not None:
            # The x-axis always tracks the current simulation time
            # so the trace fills the full chart width from left to
            # right at every tick — even when only a fraction of a
            # second of data has been recorded. Once the simulation
            # time exceeds the window the axis scrolls so the most
            # recent ``window_min`` minutes stay visible.
            if data_max <= window_min:
                x_min = 0.0
                x_max = data_max
            else:
                x_min = data_max - window_min
                x_max = data_max
            chart.options['xAxis']['min'] = x_min
            chart.options['xAxis']['max'] = x_max
        else:
            chart.options['xAxis']['min'] = 0.0
            chart.options['xAxis']['max'] = window_min
    except Exception:
        chart.options['xAxis']['min'] = 0.0
        chart.options['xAxis']['max'] = window_min

    # Legend stays disabled — the picker cells above are the legend.
    # See ``_build_chart`` for the rationale. We still keep the
    # ``legend`` key in the options dict so echart doesn't fall back
    # to its built-in default when the series list is rebuilt.
    chart.options['legend'] = {'show': False}
    # ``legend_names`` is kept above so any future hover/tooltip
    # reader can still resolve a series index → label without us
    # having to recompute it.
    _ = legend_names

    chart.update()


# ────────────────────────────────────────────────────────────────────────────
# Unified entry point (for pop-out)
# ────────────────────────────────────────────────────────────────────────────


def render_performance_monitor_unified(
    store: Any | None,
    *,
    case_slug: str,
    window_min: float = _DEFAULT_WINDOW_MIN,
    show_header: bool = True,
    popout_url: str | None = None,
    is_popout: bool = False,
    popout_id: str | None = None,
) -> None:
    _ = case_slug

    container_classes = 'pm-page w-full h-full flex-1 min-h-0 flex-nowrap overflow-hidden gap-0'
    container_style = (
        'padding: 0 !important; margin: 0 !important; gap: 0 !important;' if is_popout else ''
    )
    with ui.column().classes(container_classes).props(f'style="{container_style}"'):
        if store is None:
            ui.label('Engine not connected.').classes('text-white/70 text-sm')
            return

        bridge = getattr(store, 'bridge', None)
        if bridge is None:
            return

        _mount_unified_stripchart(
            hub=store,
            bridge=bridge,
            case_slug=case_slug,
            window_min=window_min,
            is_popout=is_popout,
            show_header=show_header,
            popout_url=popout_url,
            popout_id=popout_id,
        )


def _mount_unified_stripchart(
    *,
    hub: Any,
    bridge: Any,
    case_slug: str,
    window_min: float,
    is_popout: bool,
    show_header: bool = False,
    popout_url: str | None = None,
    popout_id: str | None = None,
) -> None:
    state = PerfMonitorState(
        hub,
        bridge,
        case_slug,
        window_min,
        is_independent=is_popout,
        popout_id=popout_id,
    )

    cell_refs: dict[str, dict[str, Any]] = {scope: {} for scope, _ in _PANEL_SECTIONS}
    status_el: dict[str, Any] = {'el': None}
    chart_ref: dict[str, Any] = {'chart': None}

    # Store dynamic UI components for rebuilding
    tab_panels_container: dict[str, Any] = {'el': None}
    tabs_ref: dict[str, Any] = {'el': None}
    tab_refs: dict[str, Any] = {}

    def _refresh_cells(scope: str | None) -> None:  # noqa: ARG001
        active_in_order = state.all_selected()
        color_by_field: dict[str, str] = {
            field_name: hub.get_field_color(field_name, active_in_order)
            for field_name in active_in_order
        }
        active = set(active_in_order)

        for s, _ in _PANEL_SECTIONS:
            for field_name, cell in cell_refs.get(s, {}).items():
                if cell is None:
                    continue
                try:
                    if field_name in active:
                        cell.classes(add='pm-cell-active', remove='pm-cell-inactive')
                        cell_color = color_by_field.get(field_name, '')
                        if cell_color:
                            cell.props(
                                f'style="border: 1px solid {cell_color} '
                                f'!important; '
                                f'background-color: {cell_color}26 '
                                f'!important; '
                                f'box-shadow: inset 0 0 0 1px '
                                f'{cell_color}55, 0 '
                                '0 6px -2px {cell_color}aa; "'
                            )
                        _repaint_cell_dot(cell, cell_color)
                    else:
                        cell.classes(add='pm-cell-inactive', remove='pm-cell-active')
                        cell.props('style=""')
                        _repaint_cell_dot(cell, '')
                except Exception:
                    pass

    def _refresh_status(scope: str | None) -> None:  # noqa: ARG001
        el = status_el.get('el')
        if el is None:
            return
        fields = state.all_selected()
        try:
            el.clear()
            with el:
                if fields:
                    active_in_order = state.all_selected()
                    color_by_field = {
                        f: hub.get_field_color(f, active_in_order) for f in active_in_order
                    }
                    for i, f in enumerate(fields):
                        if i > 0:
                            ui.label('·').classes('pm-panel-statusbar-value text-white/30 px-2')
                        c = color_by_field.get(f, '#ffffff')
                        ui.label(_format_legend_label(f)).classes(
                            'pm-panel-statusbar-value font-mono tracking-tight font-bold'
                        ).style(f'color: {c} !important;')
                else:
                    ui.label('(no signal selected)').classes(
                        'pm-panel-statusbar-value pm-panel-statusbar-value-empty'
                    )
        except Exception:
            pass

    def _update_unified_chart(scope: str | None) -> None:  # noqa: ARG001
        chart = chart_ref.get('chart')
        if chart is None:
            return
        _update_chart(
            chart=chart,
            selected_fields=state.all_selected(),
            step_history=state.step_history,
            window_min=state.window_min,
            registry=state.hub.registry,
            all_selected_fields=state.all_selected(),
            hub=hub,
        )

    def _build_unified_header_grid(scope: str, scope_fields: list[str]) -> None:
        if not scope_fields:
            ui.label('(no fields available for this scope)').classes('pm-panel-cell-empty')
            return

        with ui.row().classes(
            'pm-panel-cell-grid flex-1 min-w-0 flex-nowrap '
            'overflow-x-auto overflow-y-hidden items-center pb-1 !pt-0'
        ):
            active_in_order = state.all_selected()
            color_by_field: dict[str, str] = {
                field_name: hub.get_field_color(field_name, active_in_order)
                for field_name in active_in_order
            }
            active = set(active_in_order)

            for field_name in scope_fields:
                scope_prefix, _, tag = field_name.partition(':')
                is_active = field_name in active
                cell_color = color_by_field.get(field_name, '')
                display_tag = get_label(field_name, tag.upper())

                cell = ui.element('div').classes(
                    'pm-cell ' + ('pm-cell-active' if is_active else 'pm-cell-inactive')
                )
                if is_active and cell_color:
                    cell.props(
                        f'style="border: 1px solid {cell_color} '
                        f'!important; '
                        f'background-color: {cell_color}26 '
                        f'!important; '
                        f'box-shadow: none; "'
                    )
                with cell:
                    dot = ui.element('span').classes('pm-cell-color-dot')
                    if is_active and cell_color:
                        dot.props(f'style="background-color: {cell_color}; box-shadow: none; "')
                    else:
                        dot.props(
                            'style="background-color: #ffffff; opacity: 0.3; box-shadow: none; "'
                        )
                    with ui.column().classes('pm-cell-text'):
                        ui.label(display_tag).classes('pm-cell-tag')
                        ui.label(scope_prefix.upper()).classes('pm-cell-meta')

                cell.on(
                    'click.stop',
                    lambda _event, s=scope, f=field_name: state.toggle_field(s, f),
                )
                cell_refs[scope][field_name] = cell

    def _rebuild_panels():
        # Clear out existing references
        for scope, _ in _PANEL_SECTIONS:
            cell_refs[scope].clear()

        el = tab_panels_container.get('el')
        tabs = tabs_ref.get('el')
        if el and tabs:
            el.clear()
            with el:
                for scope, _ in _PANEL_SECTIONS:
                    with ui.tab_panel(tab_refs[scope]).classes('w-full p-2'):
                        _build_unified_header_grid(scope, state.fields_by_scope.get(scope, []))

    state.on_refresh_cells.append(_refresh_cells)
    state.on_refresh_status.append(_refresh_status)
    state.on_update_charts.append(_update_unified_chart)
    state.on_rebuild_panels.append(_rebuild_panels)

    with ui.column().classes('w-full flex-1 min-h-0 flex-nowrap overflow-hidden gap-0'):
        card_style = 'padding: 0 !important; gap: 0 !important;'
        if is_popout:
            card_style += ' border-radius: 0 !important; '
            card_style += 'border: none !important; '
            'margin: 0 !important; box-shadow: none !important;'
        with (
            ui.card()
            .classes('pm-panel w-full flex-1 min-h-0 flex-col overflow-hidden')
            .props(f'style="{card_style}"')
        ):
            if show_header:
                with (
                    ui.row()
                    .classes('pm-page-header w-full items-center justify-between flex-nowrap')
                    .props(
                        'style="background-color: transparent !important; '
                        'margin: 0 !important; '
                        'border: none !important; border-bottom: 1px '
                        'solid rgba(255, 255, 255, 0.08) !important; '
                        'border-radius: 0 !important; box-shadow: '
                        'none !important;"'
                    )
                ):
                    with ui.column().classes('gap-1'):
                        ui.label('Performance Monitoring').classes('pm-page-title')
                        ui.label(
                            f'Live signals · {window_min:g} min window · use tabs below to '
                            'select signals'
                        ).classes('pm-page-subtitle')

                    with ui.row().classes('items-center gap-2'):
                        ui.button(
                            'All inputs',
                            on_click=lambda: state.toggle_all_for_scope('input'),
                            color=None,
                        ).props('flat no-caps dense').classes('pm-action-btn')
                        ui.button(
                            'All states',
                            on_click=lambda: state.toggle_all_for_scope('state'),
                            color=None,
                        ).props('flat no-caps dense').classes('pm-action-btn')
                        ui.button(
                            'All outputs',
                            on_click=lambda: state.toggle_all_for_scope('output'),
                            color=None,
                        ).props('flat no-caps dense').classes('pm-action-btn')
                        ui.button('Clear plots', on_click=state.clear_all, color=None).props(
                            'flat no-caps dense'
                        ).classes('pm-action-btn pm-action-btn-danger')

                        with (
                            ui.button('Save', color=None)
                            .props('flat no-caps dense icon-right=expand_more')
                            .classes('pm-action-btn pm-save-btn')
                        ):
                            with ui.menu().classes('pm-save-menu'):
                                ui.menu_item(
                                    'Plot  →  PNG',
                                    lambda: _save_chart_as(
                                        chart_ref.get('chart'),
                                        'png',
                                        'performance_unified',
                                    ),
                                )
                                ui.menu_item(
                                    'Plot  →  JPEG',
                                    lambda: _save_chart_as(
                                        chart_ref.get('chart'),
                                        'jpeg',
                                        'performance_unified',
                                    ),
                                )

                        if popout_url:
                            from app.components.popout_button import (
                                render_popout_button,
                            )

                            render_popout_button(
                                popout_url,
                                tooltip='Open in New Tab',
                            )

            with ui.column().classes('w-full shrink-0 gap-0'):
                with (
                    ui.tabs()
                    .classes('w-full text-[#ffd600]')
                    .props('dense align="justify" indicator-color="amber"') as tabs
                ):
                    tabs_ref['el'] = tabs
                    for scope, title in _PANEL_SECTIONS:
                        tab_refs[scope] = ui.tab(name=scope, label=title).classes(
                            'text-[11px] font-bold tracking-wider uppercase'
                        )

                ui.separator().classes('pm-separator opacity-50')

                from nicegui import app

                tab_storage_key = (
                    f'perf_monitor_tab_{case_slug}_{popout_id}'
                    if (is_popout and popout_id)
                    else f'perf_monitor_tab_{case_slug}'
                )
                app.storage.user.setdefault(tab_storage_key, 'input')
                tabs.bind_value(app.storage.user, tab_storage_key)

                tab_panels = (
                    ui.tab_panels(tabs, value=app.storage.user[tab_storage_key])
                    .classes('w-full bg-transparent')
                    .props('animated keep-alive style="min-height: 60px; padding: 0;"')
                )
                tab_panels_container['el'] = tab_panels
                with tab_panels:
                    for scope, _title in _PANEL_SECTIONS:
                        with ui.tab_panel(tab_refs[scope]).classes('w-full p-2'):
                            _build_unified_header_grid(scope, state.fields_by_scope.get(scope, []))

                ui.separator().classes('pm-separator opacity-50')

            chart_container_classes = 'w-full flex-1 min-h-0 flex-col overflow-hidden gap-0'
            chart_container_classes += ' p-0 bg-black/40' if is_popout else ' p-4 pt-3'
            with ui.column().classes(chart_container_classes):
                statusbar_classes = 'pm-panel-statusbar w-full items-center shrink-0 z-10'
                statusbar_classes += ' mb-0' if is_popout else ' mb-4'
                with ui.row().classes(statusbar_classes):
                    ui.label('Selected').classes('pm-panel-statusbar-label')
                    status_el['el'] = ui.row().classes(
                        'items-center gap-0 flex-1 min-w-0 overflow-hidden'
                    )

                _refresh_status(None)

                with ui.element('div').classes('w-full flex-1 min-h-0 relative'):
                    chart_ref['chart'] = _build_chart(unified=True, chart_id='pm-chart-unified')

                _update_unified_chart(None)

    state.start_flush_timer()
