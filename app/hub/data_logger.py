# app/hub/data_logger.py

"""Data Logger menu-section renderer (case-agnostic).

Moved from ``app/pid/_shared/data_logger.py`` during the v1 purge —
identical behaviour, new location. Consumes the same ``bridge``
public API (``state``, ``drain_log_records``, ``set_selected_log_fields``,
``clear_logs``, ``_format_log_header``, ``_format_log_row``,
``format_record``, ``queue_status``, ``_step_log``,
``supported_modes``); pages obtain the bridge via
``hub.engine_control.bridge``.

Visual / UX style follows the **PID right drawer** (see
``app/components/right_drawer.py`` and
``app/static/css/control_panel/pid_right_drawer.css``):

- a top-level title row with an uppercase control-UI font and a
  thin separator (``.pid-right-drawer-title`` /
  ``.pid-right-drawer-separator``);
- each section gets a muted "section title" (``.pid-right-drawer-
  section-title``) immediately above its card;
- card backgrounds use ``--bg-panel`` with a hair border, the same
  treatment as the drawer items.

Layout
------

The data logger is split into **three scoped cards** (Inputs,
States, Outputs) plus one **Info** card at the bottom:

- Each scoped card exposes its log columns as a *table-header row*
  of multi-select dropdowns. The user toggles which signals show in
  that scope's log widget. The select rows are scrollable
  horizontally so wide column sets still fit.
- Below each header row sits a dedicated ``ui.log`` that streams
  rows for the selected fields in that scope only. The log line
  starts with ``realtime | step | sim_min`` and then the chosen
  signals — same row format the bridge already produces, just
  filtered per scope so each card is independently readable.
- The **Info** card at the very bottom shows status messages (Run,
  Stop, Reset, mode change, etc.) — kind ``'status'`` records
  drained from the bridge.

Bridge integration
------------------

The helper is **case-agnostic**. It only needs:

- a bridge object (anything exposing the relevant
  :class:`GenericBridge` API — ``state``, ``drain_log_records``,
  ``set_selected_log_fields``, ``clear_logs``, ``_format_log_header``,
  ``_format_log_row``, ``format_record``, ``queue_status``,
  ``_step_log``, ``supported_modes``);
- a case config object exposing ``LOOP_ORDER`` and ``LOOP_SIGNAL_MAP``
  (used as a hint for ordering columns inside each scope). The
  helper tries ``bridge.case_name`` →
  ``gateway.registry.config_registry.get_case_config`` and silently falls
  back to plain alphabetical ordering if neither is available.

The helper is what each case's ``render_<case>_data_logger()`` calls
when a bridge is wired; otherwise the placeholder
"no engine / no log file" card stays in place.
"""

from __future__ import annotations

import csv
import io
import json
from collections import deque
from datetime import datetime
from typing import Any

# pyrefly: ignore [missing-import]
from nicegui import ui

from app.ui.cell_labels import get_label, open_rename_dialog

__all__ = [
    'render_data_logger_section',
    'data_logger_unavailable',
    'write_audit_log',
]


# How often the flush timer drains the bridge's record queue.
# 300 ms ≈ 3 Hz — fast enough to read the log, slow enough that
# the DOM never chokes even when the engine is running at very
# high acceleration.
_FLUSH_INTERVAL_S: float = 0.3

# Cap on the in-memory step history used for replay when the user
# toggles field selection.  Must be large enough to hold at least
# 60 minutes of data at the slowest expected Ts (biodiesel Ts≈0.0083 min).
_STEP_HISTORY_MAXLEN: int = 9000

# Cap on rows pushed to each per-scope ``ui.log`` per flush cycle.
# At 3 Hz this means ≤ 6 rows / sec per scope — readable without
# DOM jank.
_ROWS_PER_FLUSH_CAP: int = 10

# Maximum number of rows kept in the in-memory table per scope. Older rows
# are trimmed from the front so the DOM never grows unbounded.
_REPLAY_TAIL: int = 400

# The three scopes that get their own card + log widget. The order
# here is the visual order top → bottom.
_SCOPE_ORDER: tuple[str, ...] = ('input', 'state', 'output')

# Display labels (uppercase to match right-drawer typography).
_SCOPE_TITLES: dict[str, str] = {
    'input': 'INPUTS',
    'state': 'STATES',
    'output': 'OUTPUTS',
}

# Short hint shown beside each scope title — same role the
# ``pid-right-drawer-section-title`` muted text plays in the drawer.
_SCOPE_HINTS: dict[str, str] = {
    'input': 'Manipulated values & setpoints fed into the plant',
    'state': 'Internal controller / plant states',
    'output': 'Plant outputs (PV) and measured signals',
}


# ──────────────────────────────────────────────────────────────
# Unit inference was removed — now managed by ControllerRegistry
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# Case-config resolution
# ──────────────────────────────────────────────────────────────


def _resolve_case_config(bridge: Any) -> Any:
    """Return the case-config object for the bridge, or ``None``.

    Order of resolution:
    1. ``bridge.case_cfg`` (in case a subclass has cached it).
    2. ``gateway.registry.config_registry.get_case_config(bridge.case_name)``.
    """
    cfg = getattr(bridge, 'case_cfg', None)
    if cfg is not None:
        return cfg

    case_name = getattr(bridge, 'case_name', None) or getattr(
        getattr(bridge, 'state', None),
        'case_name',
        None,
    )
    if not case_name:
        return None

    try:
        from gateway.registry.config_registry import get_case_config  # type: ignore

        return get_case_config(case_name)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────
# Field grouping by scope
# ──────────────────────────────────────────────────────────────


def _split_fields_by_scope(
    fields: list[str],
) -> dict[str, list[str]]:
    """Bucket ``input:…/state:…/output:…/meta:…`` fields by scope.

    ``meta:`` fields are folded into ``state`` so the three scope cards
    cover every available signal without a fourth card. This matches the
    way the test app treats meta as state-adjacent metadata (mode, step
    counter, …).
    """
    buckets: dict[str, list[str]] = {scope: [] for scope in _SCOPE_ORDER}

    for field in fields:
        scope, _, _ = field.partition(':')
        if scope in buckets:
            buckets[scope].append(field)
        elif scope == 'meta':
            buckets['state'].append(field)

    return buckets


def _order_fields_for_scope(
    scope_fields: list[str],
    loop_order: list[str] | None,
    loop_signal_map: dict | None,
) -> list[str]:
    """Stable order for fields inside a scope card.

    Loop signals come first in the case's declared ``LOOP_ORDER`` (each
    loop's controller/setpoint/actuator prefixes are checked against the
    tag); anything that doesn't match a loop falls after, in input
    order.
    """
    if not loop_order or not loop_signal_map or len(loop_order) <= 1:
        return list(scope_fields)

    loop_prefixes: dict[str, list[str]] = {}
    loop_plant_mvs: dict[str, str] = {}

    for loop_id, meta in loop_signal_map.items():
        prefixes = [meta[key] for key in ('controller', 'setpoint', 'actuator') if meta.get(key)]

        loop_letter = loop_id[0]
        loop_num = loop_id.split('-', 1)[1]
        prefixes.append(f'{loop_letter}T-{loop_num}')

        loop_prefixes[loop_id] = prefixes
        loop_plant_mvs[loop_id] = meta.get('plant_mv', '')

    buckets: dict[str, list[str]] = {loop_id: [] for loop_id in loop_order}
    leftovers: list[str] = []

    for field in scope_fields:
        _, _, tag = field.partition(':')

        for loop_id in loop_order:
            if tag == loop_plant_mvs.get(loop_id, ''):
                buckets[loop_id].append(field)
                break
        else:
            for loop_id in loop_order:
                if any(
                    tag.startswith(f'{prefix}.') or tag == prefix
                    for prefix in loop_prefixes[loop_id]
                ):
                    buckets[loop_id].append(field)
                    break
            else:
                leftovers.append(field)

    ordered: list[str] = []
    for loop_id in loop_order:
        ordered.extend(buckets[loop_id])
    ordered.extend(leftovers)
    return ordered


# _format_scoped_row was replaced by direct dict access in the grid.


# ──────────────────────────────────────────────────────────────
# Export helpers — CSV / JSON
# ──────────────────────────────────────────────────────────────


def _export_columns_for_scope(
    scope: str | None,
    selected_fields: list[str],
) -> list[str]:
    """Return the field list that should appear in the export.

    ``scope=None`` exports every selected field. Otherwise we filter by
    scope prefix (``input``/``state``/``output``), folding ``meta:``
    into ``state`` the same way the on-screen tabs do.
    """
    if scope is None:
        return list(selected_fields)

    return [
        field
        for field in selected_fields
        if field.partition(':')[0] == scope or (scope == 'state' and field.startswith('meta:'))
    ]


def _value_for_field(entry: dict, field_name: str) -> Any:
    """Pull a single field value out of a step-history entry.

    Mirrors the scope dispatch in :meth:`GenericBridge._format_log_row`
    so the export shows the same value the on-screen log shows. Returns
    ``None`` for unknown / missing values; the CSV writer converts that
    to an empty cell and the JSON writer keeps it as ``null``.
    """
    scope, _, tag = field_name.partition(':')

    if scope == 'input':
        return (entry.get('inputs') or {}).get(tag)
    if scope == 'state':
        return (entry.get('states') or {}).get(tag)
    if scope == 'output':
        return (entry.get('outputs') or {}).get(tag)
    if scope == 'meta':
        if tag == 'time':
            return entry.get('time_min')
        if tag == 'step':
            return entry.get('step_index')
        return None

    return None


def _build_csv_bytes(
    step_history: deque[dict],
    fields: list[str],
) -> bytes:
    """Serialise ``step_history`` rows to a UTF-8 CSV payload.

    Columns are ``step | sim_min`` followed by every entry in ``fields``
    (already scope-filtered by the caller). Values are written verbatim;
    floats keep their native repr — the user can re-parse with
    ``pandas.read_csv`` without column guessing.
    """
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')

    writer.writerow(['step', 'sim_min', *fields])

    for entry in step_history:
        if not isinstance(entry, dict):
            continue
        row = [
            entry.get('step_index'),
            entry.get('time_min'),
        ]
        for field in fields:
            row.append(_value_for_field(entry, field))
        writer.writerow(['' if v is None else v for v in row])

    return buffer.getvalue().encode('utf-8')


def _build_json_bytes(
    step_history: deque[dict],
    fields: list[str],
    *,
    case_name: str | None = None,
    scope: str | None = None,
) -> bytes:
    """Serialise ``step_history`` rows to a UTF-8 JSON payload.

    Output shape:

    ::

        {
            "case": "sthr",
            "scope": "output" | "all",
            "exported_at": "2026-06-04T18:23:11",
            "fields": ["output:T_PV", ...],
            "rows": [
                {"step": 0, "sim_min": 0.0, "output:T_PV": 25.0, ...},
                ...
            ]
        }
    """
    rows: list[dict[str, Any]] = []
    for entry in step_history:
        if not isinstance(entry, dict):
            continue
        row: dict[str, Any] = {
            'step': entry.get('step_index'),
            'sim_min': entry.get('time_min'),
        }
        for field in fields:
            row[field] = _value_for_field(entry, field)
        rows.append(row)

    payload = {
        'case': case_name,
        'scope': scope or 'all',
        'exported_at': datetime.now().isoformat(timespec='seconds'),
        'fields': list(fields),
        'rows': rows,
    }
    return json.dumps(payload, indent=2, default=str).encode('utf-8')


def _build_export_filename(
    case_name: str | None,
    scope: str | None,
    ext: str,
) -> str:
    """Compose a stable, sortable export filename.

    Example: ``sthr_output_2026-06-04T182311.csv``
    """
    stamp = datetime.now().strftime('%Y-%m-%dT%H%M%S')
    parts = [case_name or 'data_logger', scope or 'all', stamp]
    parts = [p for p in parts if p]
    return f'{"_".join(parts)}.{ext}'


def _trigger_download(
    content: bytes,
    filename: str,
    media_type: str,
) -> None:
    """Push ``content`` to the browser as a file download.

    Wraps :func:`ui.download.content` with a fallback for older NiceGUI
    builds where the helper isn't available — in that case we surface an
    actionable ``ui.notify`` instead of silently failing.
    """
    try:
        ui.download.content(content, filename, media_type)
        ui.notify(f'Saved {filename}', color='positive')
    except AttributeError:
        # Pre-2.14 NiceGUI: fall back to the legacy ui.download(...).
        try:
            ui.download(content, filename)  # type: ignore[misc]
            ui.notify(f'Saved {filename}', color='positive')
        except Exception:
            ui.notify(
                'Download not supported by this NiceGUI version',
                color='warning',
            )
    except Exception as exc:  # noqa: BLE001
        ui.notify(f'Save failed: {exc}', color='negative')


# ──────────────────────────────────────────────────────────────
# Public API — placeholder for "no engine" case
# ──────────────────────────────────────────────────────────────


def _build_grid_row(entry_like: Any, fields: list[str]) -> dict[str, Any]:
    if not isinstance(entry_like, dict):
        try:
            entry = {
                'step_index': getattr(entry_like, 'step_index', -1),
                'time_min': getattr(entry_like, 'time_min', -1.0),
                'inputs': getattr(entry_like, 'inputs', {}),
                'states': getattr(entry_like, 'states', {}),
                'outputs': getattr(entry_like, 'outputs', {}),
            }
        except Exception:
            entry = {}
    else:
        entry = entry_like

    step = entry.get('step_index')
    sim = entry.get('time_min')
    row = {
        'id': (str(step) if step is not None else str(datetime.now().timestamp())),
        'realtime': datetime.now().strftime('%Y-%m-%d | %H:%M:%S'),
        'step': step,
        'sim_min': f'{sim:.2f}' if isinstance(sim, float) else sim,
    }
    for field in fields:
        val = _value_for_field(entry, field)
        if isinstance(val, float):
            row[field] = f'{val:.3f}'
        else:
            row[field] = val
    return row


def data_logger_unavailable(message: str | None = None) -> None:
    """Render the original "no log file / no entries" placeholder."""
    fallback_message = message or 'No log entries yet. Connect an engine to start logging data.'

    with ui.column().classes('data-logger-root'):
        with ui.column().classes('gap-1'):
            ui.label('Data Logger').classes('data-logger-page-title')
            ui.label('Engine not connected').classes('data-logger-page-subtitle')
        ui.separator().classes('data-logger-separator')

        with ui.card().classes('data-logger-scope-card'):
            ui.label('Log File Location').classes('data-logger-scope-title')
            ui.label('(no log file — engine not connected)').classes(
                'data-logger-hint',
            )

        with ui.card().classes('data-logger-scope-card'):
            ui.label('Recent Entries').classes('data-logger-scope-title')
            ui.label(fallback_message).classes('data-logger-hint')


# ──────────────────────────────────────────────────────────────
# Public API — main renderer
# ──────────────────────────────────────────────────────────────


def _repaint_cell_dot(cell: Any, color: str) -> None:
    try:
        dot = next(
            (
                child
                for child in cell.default_slot.children
                if 'data-logger-cell-color-dot' in getattr(child, '_classes', [])
            ),
            None,
        )
        if dot:
            if color:
                dot.props(f'style="background-color: {color}; box-shadow: 0 0 4px {color}; "')
            else:
                dot.props('style="background-color: #ffffff; opacity: 0.3; box-shadow: none; "')
    except Exception:
        pass


class DataLoggerState:
    """Shared state for Data Logger (both stacked and unified layouts)."""

    def __init__(
        self,
        hub: Any,
        case_slug: str,
        loop_order: list,
        loop_signal_map: dict,
        is_independent: bool = False,
        popout_id: str | None = None,
    ):
        self.hub = hub
        self.bridge = hub.bridge
        self.case_slug = case_slug
        self.loop_order = loop_order
        self.loop_signal_map = loop_signal_map
        self.is_independent = is_independent
        self.popout_id = popout_id
        self.storage_key = (
            f'dl_selected_{self.case_slug}_{self.popout_id}'
            if (self.is_independent and self.popout_id)
            else f'dl_selected_{self.case_slug}'
        )

        self.watermark = [-1]

        self.last_seen_reset_counter = [getattr(self.hub, '_reset_counter', 0)]
        self.available_fields = list(getattr(self.bridge.state, 'available_log_fields', []) or [])

        self.on_refresh_pickers = []
        self.on_replay_scopes = []
        self.on_push_info = []
        self.on_push_rows = []
        self.on_clear_widgets = []
        self.on_rebuild_grids = []

        from nicegui import app

        self.last_seen_audit_counter = app.storage.user.get(f'audit_log_counter_{case_slug}', 0)
        write_audit_log(
            self.case_slug,
            'Page reloaded / UI initialized',
            bridge=self.bridge,
        )

        if not hasattr(self.hub, 'dl_selected_fields_map'):
            self.hub.dl_selected_fields_map = {}

        self.session_key = self.popout_id if (self.is_independent and self.popout_id) else 'main'

        try:
            saved = app.storage.user.get(self.storage_key)
            if saved is not None:
                self.hub.dl_selected_fields_map[self.session_key] = list(saved)
            else:
                self.hub.dl_selected_fields_map[self.session_key] = list(
                    self.hub.dl_selected_fields_map.get(self.session_key, [])
                )
        except Exception:
            self.hub.dl_selected_fields_map[self.session_key] = list(
                self.hub.dl_selected_fields_map.get(self.session_key, [])
            )

        if hasattr(self.hub, 'update_bridge_selected_fields'):
            self.hub.update_bridge_selected_fields()

    def commit_selection(self, new_fields: list[str]) -> None:
        available = list(getattr(self.bridge.state, 'available_log_fields', []) or [])
        ordered = [field for field in available if field in set(new_fields)]
        if not hasattr(self.hub, 'dl_selected_fields_map'):
            self.hub.dl_selected_fields_map = {}
        self.hub.dl_selected_fields_map[self.session_key] = ordered
        try:
            from nicegui import app

            app.storage.user[self.storage_key] = ordered
        except Exception:
            pass
        if hasattr(self.hub, 'update_bridge_selected_fields'):
            self.hub.update_bridge_selected_fields()

    def selected_for_scope(self, scope: str) -> list[str]:
        current = self.all_selected()
        return [
            field
            for field in current
            if field.partition(':')[0] == scope or (scope == 'state' and field.startswith('meta:'))
        ]

    def all_selected(self) -> list[str]:
        if not hasattr(self.hub, 'dl_selected_fields_map'):
            self.hub.dl_selected_fields_map = {}
        return list(self.hub.dl_selected_fields_map.get(self.session_key, []))

    def toggle_field(self, field_name: str) -> None:
        current = self.all_selected()

        if field_name in current:
            current = [f for f in current if f != field_name]
            write_audit_log(
                self.case_slug,
                f"Deselected '{field_name}' for logging",
                bridge=self.bridge,
            )
        else:
            current.append(field_name)
            write_audit_log(
                self.case_slug,
                f"Selected '{field_name}' for logging",
                bridge=self.bridge,
            )

        self.commit_selection(current)
        for cb in self.on_refresh_pickers:
            cb(None)
        for cb in self.on_replay_scopes:
            cb(None)

    def use_outputs(self) -> None:
        try:
            outputs = [
                field
                for field in getattr(self.bridge.state, 'available_log_fields', [])
                if field.startswith('output:')
            ]
            self.commit_selection(outputs)
            write_audit_log(
                self.case_slug,
                'Selected All Outputs for logging',
                bridge=self.bridge,
            )
        except Exception:
            pass
        for cb in self.on_refresh_pickers:
            cb(None)
        for cb in self.on_replay_scopes:
            cb(None)

    def use_all(self) -> None:
        try:
            all_fields = list(getattr(self.bridge.state, 'available_log_fields', []))
            self.commit_selection(all_fields)
            write_audit_log(
                self.case_slug,
                'Selected All Fields for logging',
                bridge=self.bridge,
            )
        except Exception:
            pass
        for cb in self.on_refresh_pickers:
            cb(None)
        for cb in self.on_replay_scopes:
            cb(None)

    def clear_all_logs(self) -> None:
        try:
            self.bridge.clear_logs()
        except Exception:
            pass
        for cb in self.on_clear_widgets:
            cb()
        self.watermark[0] = -1
        write_audit_log(self.case_slug, 'Cleared all log entries', bridge=self.bridge)
        for cb in self.on_refresh_pickers:
            cb(None)
        for cb in self.on_replay_scopes:
            cb(None)
        from nicegui import ui

        ui.notify('Logs cleared', color='positive')

    def toggle_all_for_scope(self, scope: str) -> None:
        try:
            available_for_scope = [
                field
                for field in getattr(self.bridge.state, 'available_log_fields', [])
                if field.startswith(f'{scope}:') or (scope == 'state' and field.startswith('meta:'))
            ]
            if not available_for_scope:
                return
            current = self.all_selected()
            current_set = set(current)
            scope_set = set(available_for_scope)

            # Check if ALL fields of this scope are currently selected
            all_selected = all(f in current_set for f in available_for_scope)

            if all_selected:
                # Remove all fields of this scope
                new_selection = [f for f in current if f not in scope_set]
                write_audit_log(
                    self.case_slug, f'Deselected All {scope.title()}s', bridge=self.bridge
                )
            else:
                # Add all fields of this scope
                new_selection = current + [f for f in available_for_scope if f not in current_set]
                write_audit_log(
                    self.case_slug, f'Selected All {scope.title()}s', bridge=self.bridge
                )

            self.commit_selection(new_selection)
        except Exception:
            pass
        for cb in self.on_refresh_pickers:
            cb(None)
        for cb in self.on_replay_scopes:
            cb(None)

    def start_flush_timer(self) -> None:
        from nicegui import ui

        def _flush_log() -> None:
            current_reset_counter = getattr(self.hub, '_reset_counter', 0)

            if current_reset_counter > self.last_seen_reset_counter[0]:
                self.watermark[0] = -1
                for cb in self.on_clear_widgets:
                    cb()
                self.last_seen_reset_counter[0] = current_reset_counter

            try:
                current_available = sorted(
                    getattr(self.bridge.state, 'available_log_fields', []) or []
                )
                if current_available != sorted(self.available_fields):
                    self.available_fields[:] = current_available
                    for cb in self.on_rebuild_grids:
                        cb()
                    for cb in self.on_replay_scopes:
                        cb(None)
            except Exception:
                pass

            try:
                log_records = self.bridge.drain_log_records()
            except Exception:
                log_records = []

            new_step_entries = self.hub.get_history_since(self.watermark[0])

            if new_step_entries:
                self.watermark[0] = max(int(e.get('step_index', -1)) for e in new_step_entries)
                for cb in self.on_push_rows:
                    cb(new_step_entries)

            for record in log_records:
                kind = getattr(record, 'kind', None)
                if kind == 'status':
                    mode_str = getattr(record, 'mode', '') or ''
                    mode_part = f'[{mode_str:<10}] ' if mode_str else ''
                    message = getattr(record, 'message', '')
                    msg_lower = str(message).lower()
                    if any(k in msg_lower for k in ('error', 'failed', 'exception')):
                        level = 'ERR '
                    elif any(k in msg_lower for k in ('stopped', 'paused', 'warn')):
                        level = 'WARN'
                    else:
                        level = 'INFO'
                    write_audit_log(
                        self.case_slug,
                        f'{level} {mode_part}{message}',
                        bridge=self.bridge,
                    )
                elif kind == 'header':
                    pass

            try:
                from nicegui import app

                counter = app.storage.user.get(f'audit_log_counter_{self.case_slug}', 0)
                last_seen = getattr(self, 'last_seen_audit_counter', 0)
                if counter > last_seen:
                    history = app.storage.user.get(f'audit_log_{self.case_slug}') or []
                    diff = counter - last_seen
                    if diff > 0 and history:
                        # Grab the newly added lines (at most all of history)
                        new_lines = history[-diff:] if diff <= len(history) else history
                        for line in new_lines:
                            for cb in self.on_push_info:
                                cb(line)
                    self.last_seen_audit_counter = counter
            except Exception:
                pass

        ui.timer(_FLUSH_INTERVAL_S, _flush_log)


def render_data_logger_section(
    store: Any | None,
    *,
    popout_url: str | None = None,
    is_popout: bool = False,
    _show_header: bool = False,
) -> None:
    if store is None:
        ui.label('Engine not connected.').classes('text-white/70 text-sm')
        return

    hub = store
    bridge = getattr(hub, 'bridge', None)
    if bridge is None:
        return

    case_cfg = _resolve_case_config(bridge)
    loop_order = getattr(case_cfg, 'LOOP_ORDER', None) or []
    loop_signal_map = getattr(case_cfg, 'LOOP_SIGNAL_MAP', None) or {}
    case_slug = getattr(bridge, 'case_name', None) or 'unknown'

    state = DataLoggerState(hub, case_slug, loop_order, loop_signal_map, is_independent=is_popout)

    scope_log_refs: dict[str, dict[str, Any]] = {scope: {'log': None} for scope in _SCOPE_ORDER}
    info_log_ref: dict[str, Any] = {'log': None}
    scope_select_refs: dict[str, dict[str, Any]] = {
        scope: {'cells': {}, 'grid_container': None} for scope in _SCOPE_ORDER
    }

    def _update_grid_columns(scope: str) -> None:
        table = scope_log_refs[scope].get('log')
        if not table:
            return
        fields = state.selected_for_scope(scope)
        col_defs = [
            {
                'name': 'realtime',
                'label': 'REALTIME',
                'field': 'realtime',
                'align': 'left',
                'classes': 'data-logger-grid-cell-fixed',
                'headerClasses': 'data-logger-grid-header',
            },
            {
                'name': 'step',
                'label': 'STEP',
                'field': 'step',
                'align': 'left',
                'classes': 'data-logger-grid-cell-fixed',
                'headerClasses': 'data-logger-grid-header',
            },
            {
                'name': 'sim_min',
                'label': 'SIM_MIN',
                'field': 'sim_min',
                'align': 'left',
                'classes': 'data-logger-grid-cell-fixed',
                'headerClasses': 'data-logger-grid-header',
            },
        ]
        for field in fields:
            _, _, tag = field.partition(':')
            display_tag = get_label(field, tag.upper())
            unit = hub.registry.get_unit_for(field)
            header = f'{display_tag} [{unit}]' if unit else display_tag
            col_defs.append(
                {
                    'name': field,
                    'label': header,
                    'field': field,
                    'align': 'right',
                    'classes': 'data-logger-grid-cell',
                    'headerClasses': 'data-logger-grid-header',
                }
            )
        table._props['columns'] = col_defs
        table.update()

    def _refresh_pickers(scope: str | None) -> None:
        scopes = [scope] if scope else _SCOPE_ORDER
        active_in_order = state.all_selected()
        color_by_field = {
            field_name: hub.get_field_color(field_name, active_in_order)
            for field_name in active_in_order
        }
        active = set(active_in_order)

        for s in scopes:
            cells = scope_select_refs[s].get('cells') or {}
            for field_name, cell in cells.items():
                if cell is None:
                    continue
                try:
                    if field_name in active:
                        cell.classes(
                            add='data-logger-header-cell-active',
                            remove='data-logger-header-cell-inactive',
                        )
                        cell_color = color_by_field.get(field_name, '')
                        if cell_color:
                            cell.props(
                                f'style="border: 1px solid {cell_color} '
                                f'!important; '
                                f'background-color: {cell_color}26 '
                                f'!important; '
                                f'box-shadow: inset 0 0 0 1px '
                                f'{cell_color}55, '
                                f'0 0 6px -2px {cell_color}aa; "'
                            )
                        _repaint_cell_dot(cell, cell_color)
                    else:
                        cell.classes(
                            add='data-logger-header-cell-inactive',
                            remove='data-logger-header-cell-active',
                        )
                        cell.props('style=""')
                        _repaint_cell_dot(cell, '')
                except Exception:
                    pass

    def _replay_scopes(scope: str | None) -> None:
        scopes = [scope] if scope else _SCOPE_ORDER
        for s in scopes:
            table = scope_log_refs[s].get('log')
            if table is None:
                continue
            fields = state.selected_for_scope(s)
            _update_grid_columns(s)
            if not fields:
                table.rows = []
                table.update()
                continue
            _REPLAY_TAIL = 400
            rows = []
            for entry in list(state.hub._history)[-_REPLAY_TAIL:]:
                if not isinstance(entry, dict):
                    continue
                rows.append(_build_grid_row(entry, fields))
            table.rows = rows
            table.update()

    def _push_info(line: str) -> None:
        info_widget = info_log_ref.get('log')
        if info_widget:
            try:
                info_widget.push(line)
            except Exception:
                pass

    def _push_rows(new_step_entries: list[dict]) -> None:
        _batch_by_scope: dict[str, list[dict]] = {s: [] for s in _SCOPE_ORDER}
        entries_to_push = new_step_entries[-_ROWS_PER_FLUSH_CAP:]
        for entry in entries_to_push:
            for s in _SCOPE_ORDER:
                fields = state.selected_for_scope(s)
                if not fields:
                    continue
                _batch_by_scope[s].append(_build_grid_row(entry, fields))
        for s in _SCOPE_ORDER:
            table = scope_log_refs[s].get('log')
            if table and _batch_by_scope[s]:
                table.rows.extend(_batch_by_scope[s])
                if len(table.rows) > _REPLAY_TAIL:
                    table.rows = table.rows[-_REPLAY_TAIL:]
                table.update()

    def _clear_widgets() -> None:
        for s in _SCOPE_ORDER:
            table = scope_log_refs[s].get('log')
            if table:
                try:
                    table.rows = []
                    table.update()
                except Exception:
                    pass
        info_widget = info_log_ref.get('log')
        if info_widget:
            try:
                info_widget.clear()
            except Exception:
                pass

    def _rebuild_grids() -> None:
        for s in _SCOPE_ORDER:
            container = scope_select_refs[s].get('grid_container')
            if container:
                try:
                    container.clear()
                    with container:
                        _build_header_grid(s)
                except Exception:
                    pass

    state.on_refresh_pickers.append(_refresh_pickers)
    state.on_replay_scopes.append(_replay_scopes)
    state.on_push_info.append(_push_info)
    state.on_push_rows.append(_push_rows)
    state.on_clear_widgets.append(_clear_widgets)
    state.on_rebuild_grids.append(_rebuild_grids)

    def _on_cell_renamed(field_name: str, cell: Any) -> None:
        _, _, tag = field_name.partition(':')
        new_display = get_label(field_name, tag.upper())
        try:
            for child in cell.default_slot.children:
                if 'data-logger-header-cell-tag' in getattr(child, '_classes', []):
                    child.set_text(new_display)
                    break
        except Exception:
            pass

    def _save_scope_as(scope: str | None, fmt: str) -> None:
        if not state.hub._history:
            ui.notify('No log entries to save yet.', color='warning')
            return
        selected = state.all_selected()
        fields = _export_columns_for_scope(scope, selected)
        if not fields and scope is not None:
            fields = _split_fields_by_scope(list(bridge.state.available_log_fields)).get(scope, [])
            fields = _order_fields_for_scope(fields, loop_order, loop_signal_map)
        if not fields:
            ui.notify('No columns selected to save.', color='warning')
            return
        case_name = getattr(bridge, 'case_name', None) or getattr(
            getattr(bridge, 'state', None), 'case_name', None
        )
        if fmt == 'csv':
            payload = _build_csv_bytes(state.hub._history, fields)
            filename = _build_export_filename(case_name, scope, 'csv')
            _trigger_download(payload, filename, 'text/csv')
        elif fmt == 'json':
            payload = _build_json_bytes(
                state.hub._history, fields, case_name=case_name, scope=scope
            )
            filename = _build_export_filename(case_name, scope, 'json')
            _trigger_download(payload, filename, 'application/json')
        else:
            ui.notify(f'Unknown export format: {fmt}', color='negative')

    def _build_header_grid(scope: str) -> None:
        cells_ref = scope_select_refs[scope]['cells'] = {}
        with ui.row().classes('data-logger-header-grid'):
            for prefix_label in ('realtime', 'step', 'sim_min'):
                with ui.element('div').classes(
                    'data-logger-header-cell data-logger-header-cell-readonly'
                ):
                    dot = ui.element('span').classes('data-logger-cell-color-dot')
                    dot.props(
                        'style="background-color: #ffd54f; '
                        'opacity: 1; box-shadow: 0 0 4px #ffd54f; "'
                    )
                    with ui.column().classes('data-logger-header-cell-text'):
                        ui.label(prefix_label).classes('data-logger-header-cell-tag')
                        ui.label('fixed').classes('data-logger-header-cell-meta')

            scoped = _split_fields_by_scope(list(bridge.state.available_log_fields)).get(scope, [])
            options = _order_fields_for_scope(scoped, loop_order, loop_signal_map)
            active_in_order = state.all_selected()
            color_by_field = {
                field_name: hub.get_field_color(field_name, active_in_order)
                for field_name in active_in_order
            }
            active = set(active_in_order)

            if not options:
                ui.label('(no fields available for this scope)').classes(
                    'data-logger-header-grid-empty'
                )
                return

            for field_name in options:
                _, _, tag = field_name.partition(':')
                is_active = field_name in active
                cell_color = color_by_field.get(field_name, '')
                unit = hub.registry.get_unit_for(field_name)
                display_tag = get_label(field_name, tag.upper())

                cell = ui.element('div').classes(
                    'data-logger-header-cell '
                    + (
                        'data-logger-header-cell-active'
                        if is_active
                        else 'data-logger-header-cell-inactive'
                    )
                )
                if is_active and cell_color:
                    cell.props(
                        f'style="border: 1px solid {cell_color} '
                        f'!important; '
                        f'background-color: {cell_color}26 '
                        f'!important; '
                        f'box-shadow: inset 0 0 0 1px '
                        f'{cell_color}55, '
                        f'0 0 6px -2px {cell_color}aa; "'
                    )
                with cell:
                    dot = ui.element('span').classes('data-logger-cell-color-dot')
                    if is_active and cell_color:
                        dot.props(
                            f'style="background-color: {cell_color}; '
                            f'box-shadow: 0 0 4px {cell_color}; "'
                        )
                    else:
                        dot.props(
                            'style="background-color: #ffffff; opacity: 0.3; box-shadow: none; "'
                        )
                    with ui.column().classes('data-logger-header-cell-text'):
                        ui.label(display_tag).classes('data-logger-header-cell-tag')
                        ui.label(unit or '·').classes('data-logger-header-cell-meta')

                cell.on(
                    'click.stop',
                    lambda _event, f=field_name: state.toggle_field(f),
                )

                def _make_dblclick_handler(fn=field_name, c=cell):
                    return lambda e: open_rename_dialog(
                        fn,
                        get_label(fn, fn.partition(':')[2].upper()),
                        on_confirm=lambda: _on_cell_renamed(fn, c),
                    )

                cell.on('dblclick', _make_dblclick_handler())
                cells_ref[field_name] = cell

    def _build_scope_card(scope: str) -> None:
        with ui.card().classes('data-logger-scope-card'):
            with ui.row().classes('data-logger-scope-card-header'):
                with ui.column().classes('data-logger-scope-title-group'):
                    ui.label(_SCOPE_TITLES[scope]).classes('data-logger-scope-title')
                    ui.label(_SCOPE_HINTS[scope]).classes('data-logger-scope-hint')
                with (
                    ui.button(icon='save', color=None)
                    .props('flat dense round size=sm')
                    .classes('data-logger-scope-save-btn')
                ):
                    with ui.menu().classes('data-logger-save-menu'):
                        ui.menu_item(
                            f'{_SCOPE_TITLES[scope].title()}  →  CSV',
                            lambda _, s=scope: _save_scope_as(s, 'csv'),
                        )
                        ui.menu_item(
                            f'{_SCOPE_TITLES[scope].title()}  →  JSON',
                            lambda _, s=scope: _save_scope_as(s, 'json'),
                        )
            # Body wrapper — mirrors .pm-panel-body (header border-bottom acts
            # as separator)
            with ui.column().classes('data-logger-scope-card-body'):
                header_container = ui.element('div').classes('data-logger-header-container')
                scope_select_refs[scope]['grid_container'] = header_container
                with header_container:
                    _build_header_grid(scope)

                table = (
                    ui.table(columns=[], rows=[], row_key='id', pagination=None)
                    .classes('data-logger-grid')
                    .props('dense flat bordered wrap-cells=false')
                    .style('height: 250px;')
                )
                scope_log_refs[scope]['log'] = table
                ui.run_javascript(f"""
                    setTimeout(() => {{
                        try {{
                            const comp = getElement({table.id});
                            if (!comp) return;
                            const el = comp.$el.querySelector(
                                '.q-table__middle'
                            );
                            if (!el) return;
                            el.scrollTop = el.scrollHeight;
                            let isAtBottom = true;
                            el.addEventListener('scroll', () => {{
                                isAtBottom = Math.abs(
                                    el.scrollHeight - el.scrollTop
                                    - el.clientHeight
                                ) < 50;
                            }}, {{ passive: true }});
                            const tbody = el.querySelector('tbody');
                            if (!tbody) return;
                            const observer = new MutationObserver(() => {{
                                if (isAtBottom) {{
                                    el.scrollTop = el.scrollHeight; }}
                            }});
                            observer.observe(tbody, {{ childList: true }});
                        }} catch(e) {{}}
                    }}, 500);
                """)

    with ui.column().classes('data-logger-root'):
        with ui.row().classes('data-logger-page-title-row'):
            with ui.column().classes('gap-1'):
                ui.label('Data Logger').classes('data-logger-page-title')
                ui.label('Live signals · click cells to toggle log columns').classes(
                    'data-logger-page-subtitle'
                )
            with ui.row().classes('data-logger-page-actions'):
                ui.button(
                    'All inputs',
                    on_click=lambda: state.toggle_all_for_scope('input'),
                    color=None,
                ).props('flat no-caps dense').classes('data-logger-action-btn')
                ui.button(
                    'All states',
                    on_click=lambda: state.toggle_all_for_scope('state'),
                    color=None,
                ).props('flat no-caps dense').classes('data-logger-action-btn')
                ui.button(
                    'All outputs',
                    on_click=lambda: state.toggle_all_for_scope('output'),
                    color=None,
                ).props('flat no-caps dense').classes('data-logger-action-btn')
                ui.button('Clear log', on_click=state.clear_all_logs, color=None).props(
                    'flat no-caps dense'
                ).classes('data-logger-action-btn data-logger-action-btn-danger')
                with (
                    ui.button('Save', color=None)
                    .props('flat no-caps dense icon-right=expand_more')
                    .classes('data-logger-action-btn data-logger-save-btn')
                ):
                    with ui.menu().classes('data-logger-save-menu'):
                        ui.menu_item(
                            'All scopes  →  CSV',
                            lambda: _save_scope_as(None, 'csv'),
                        )
                        ui.menu_item(
                            'All scopes  →  JSON',
                            lambda: _save_scope_as(None, 'json'),
                        )
                        ui.separator()
                        for scope_key in _SCOPE_ORDER:
                            ui.menu_item(
                                f'{_SCOPE_TITLES[scope_key].title()} only  →  CSV',
                                lambda _, s=scope_key: _save_scope_as(s, 'csv'),
                            )
                            ui.menu_item(
                                f'{_SCOPE_TITLES[scope_key].title()} only  →  JSON',
                                lambda _, s=scope_key: _save_scope_as(s, 'json'),
                            )
                if popout_url:
                    from app.components.popout_button import (
                        render_popout_button,
                    )

                    render_popout_button(popout_url, classes='data-logger-action-btn')

        ui.separator().classes('data-logger-separator')

        for scope in _SCOPE_ORDER:
            _build_scope_card(scope)

        with ui.card().classes('data-logger-scope-card data-logger-info-card'):
            with ui.row().classes('data-logger-scope-card-header'):
                ui.label('INFO').classes('data-logger-scope-title')
                ui.label('Run / Stop / Reset, mode changes, status messages').classes(
                    'data-logger-scope-hint'
                )
            # Body wrapper — header border-bottom acts as separator
            with ui.column().classes('data-logger-scope-card-body'):
                info_log = ui.log(max_lines=200).classes('data-logger-log data-logger-info-log')
                info_log_ref['log'] = info_log

                try:
                    from nicegui import app

                    history = app.storage.user.get(f'audit_log_{case_slug}') or []
                    counter = app.storage.user.get(f'audit_log_counter_{case_slug}', 0)
                    for line in history:
                        info_log.push(line)
                    state.last_seen_audit_counter = counter
                except Exception:
                    pass

        _replay_scopes(None)
        ui.element('div').classes('min-h-[0.5rem] w-full flex-shrink-0')
        state.start_flush_timer()


def render_data_logger_unified(
    store: Any | None,
    *,
    case_slug: str,
    show_header: bool = True,
    popout_url: str | None = None,
    is_popout: bool = False,
    popout_id: str | None = None,
) -> None:
    container_classes = 'data-logger-root w-full flex-1 min-h-0 '
    'flex-nowrap overflow-hidden gap-0'
    container_style = (
        'padding: 0 !important; margin: 0 !important; gap: 0 !important; '
        'height: 100% !important; min-height: 0 !important;'
        if is_popout
        else ''
    )
    with ui.column().classes(container_classes).props(f'style="{container_style}"'):
        if store is None:
            ui.label('Engine not connected.').classes('text-white/70 text-sm')
            return

        bridge = getattr(store, 'bridge', None)
        if bridge is None:
            return

        _mount_unified_log_widget(
            hub=store,
            case_slug=case_slug,
            is_popout=is_popout,
            show_header=show_header,
            popout_url=popout_url,
            popout_id=popout_id,
        )


def _mount_unified_log_widget(
    *,
    hub: Any,
    case_slug: str,
    is_popout: bool,
    show_header: bool = False,
    popout_url: str | None = None,
    popout_id: str | None = None,
) -> None:
    bridge = getattr(hub, 'bridge', None)
    if bridge is None:
        ui.label('Simulation bridge not available.').classes('text-white/70 p-4')
        return
    case_cfg = _resolve_case_config(bridge)
    loop_order = getattr(case_cfg, 'LOOP_ORDER', None) or []
    loop_signal_map = getattr(case_cfg, 'LOOP_SIGNAL_MAP', None) or {}

    state = DataLoggerState(
        hub,
        case_slug,
        loop_order,
        loop_signal_map,
        is_independent=is_popout,
        popout_id=popout_id,
    )

    unified_log_ref: dict[str, Any] = {'log': None}
    info_log_ref: dict[str, Any] = {'log': None}
    scope_select_refs: dict[str, dict[str, Any]] = {
        scope: {'cells': {}, 'grid_container': None} for scope in _SCOPE_ORDER
    }
    tab_panels_container: dict[str, Any] = {'el': None}
    tabs_ref: dict[str, Any] = {'el': None}
    tab_refs: dict[str, Any] = {}

    def _update_grid_columns() -> None:
        table = unified_log_ref.get('log')
        if not table:
            return
        fields = state.all_selected()
        col_defs = [
            {
                'name': 'realtime',
                'label': 'REALTIME',
                'field': 'realtime',
                'align': 'left',
                'classes': 'data-logger-grid-cell-fixed',
                'headerClasses': 'data-logger-grid-header',
            },
            {
                'name': 'step',
                'label': 'STEP',
                'field': 'step',
                'align': 'left',
                'classes': 'data-logger-grid-cell-fixed',
                'headerClasses': 'data-logger-grid-header',
            },
            {
                'name': 'sim_min',
                'label': 'SIM_MIN',
                'field': 'sim_min',
                'align': 'left',
                'classes': 'data-logger-grid-cell-fixed',
                'headerClasses': 'data-logger-grid-header',
            },
        ]
        for field in fields:
            _, _, tag = field.partition(':')
            display_tag = get_label(field, tag.upper())
            unit = hub.registry.get_unit_for(field)
            header = f'{display_tag} [{unit}]' if unit else display_tag
            col_defs.append(
                {
                    'name': field,
                    'label': header,
                    'field': field,
                    'align': 'right',
                    'classes': 'data-logger-grid-cell',
                    'headerClasses': 'data-logger-grid-header',
                }
            )
        table._props['columns'] = col_defs
        table.update()

    def _refresh_pickers(scope: str | None) -> None:
        scopes = [scope] if scope else _SCOPE_ORDER
        active_in_order = state.all_selected()
        color_by_field = {
            field_name: hub.get_field_color(field_name, active_in_order)
            for field_name in active_in_order
        }
        active = set(active_in_order)

        for s in scopes:
            cells = scope_select_refs[s].get('cells') or {}
            for field_name, cell in cells.items():
                if cell is None:
                    continue
                try:
                    if field_name in active:
                        cell.classes(
                            add='data-logger-header-cell-active',
                            remove='data-logger-header-cell-inactive',
                        )
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
                        cell.classes(
                            add='data-logger-header-cell-inactive',
                            remove='data-logger-header-cell-active',
                        )
                        cell.props('style=""')
                        _repaint_cell_dot(cell, '')
                except Exception:
                    pass

    def _replay_scopes(scope: str | None) -> None:  # noqa: ARG001
        table = unified_log_ref.get('log')
        if not table:
            return
        fields = state.all_selected()
        _update_grid_columns()
        if not fields:
            table.rows = []
            table.update()
            return

        rows = []
        for entry in list(state.hub._history)[-_REPLAY_TAIL:]:
            if not isinstance(entry, dict):
                continue
            rows.append(_build_grid_row(entry, fields))
        table.rows = rows
        table.update()

    def _push_info(line: str) -> None:
        info_widget = info_log_ref.get('log')
        if info_widget:
            try:
                info_widget.push(line)
            except Exception:
                pass

    def _push_rows(new_step_entries: list[dict]) -> None:
        table = unified_log_ref.get('log')
        if not table:
            return
        fields = state.all_selected()
        if not fields:
            return

        rows = []
        entries_to_push = new_step_entries[-_ROWS_PER_FLUSH_CAP:]
        for entry in entries_to_push:
            rows.append(_build_grid_row(entry, fields))

        if rows:
            table.rows.extend(rows)
            if len(table.rows) > _REPLAY_TAIL:
                table.rows = table.rows[-_REPLAY_TAIL:]
            table.update()

    def _clear_widgets() -> None:
        table = unified_log_ref.get('log')
        if table:
            try:
                table.rows = []
                table.update()
            except Exception:
                pass
        info_widget = info_log_ref.get('log')
        if info_widget:
            try:
                info_widget.clear()
            except Exception:
                pass

    def _rebuild_grids() -> None:
        for s in _SCOPE_ORDER:
            container = scope_select_refs[s].get('grid_container')
            if container:
                try:
                    container.clear()
                    with container:
                        _build_header_grid(s)
                except Exception:
                    pass

    state.on_refresh_pickers.append(_refresh_pickers)
    state.on_replay_scopes.append(_replay_scopes)
    state.on_push_info.append(_push_info)
    state.on_push_rows.append(_push_rows)
    state.on_clear_widgets.append(_clear_widgets)
    state.on_rebuild_grids.append(_rebuild_grids)

    def _on_cell_renamed(field_name: str, cell: Any) -> None:
        _, _, tag = field_name.partition(':')
        new_display = get_label(field_name, tag.upper())
        try:
            for child in cell.default_slot.children:
                if 'data-logger-header-cell-tag' in getattr(child, '_classes', []):
                    child.set_text(new_display)
                    break
        except Exception:
            pass

    def _save_scope_as(scope: str | None, fmt: str) -> None:
        if not state.hub._history:
            ui.notify('No log entries to save yet.', color='warning')
            return
        selected = state.all_selected()
        fields = _export_columns_for_scope(scope, selected)
        if not fields and scope is not None:
            fields = _split_fields_by_scope(list(bridge.state.available_log_fields)).get(scope, [])
            fields = _order_fields_for_scope(fields, loop_order, loop_signal_map)
        if not fields:
            ui.notify('No columns selected to save.', color='warning')
            return
        case_name = getattr(bridge, 'case_name', None) or getattr(
            getattr(bridge, 'state', None), 'case_name', None
        )
        if fmt == 'csv':
            payload = _build_csv_bytes(state.hub._history, fields)
            filename = _build_export_filename(case_name, scope, 'csv')
            _trigger_download(payload, filename, 'text/csv')
        elif fmt == 'json':
            payload = _build_json_bytes(
                state.hub._history, fields, case_name=case_name, scope=scope
            )
            filename = _build_export_filename(case_name, scope, 'json')
            _trigger_download(payload, filename, 'application/json')
        else:
            ui.notify(f'Unknown export format: {fmt}', color='negative')

    def _build_header_grid(scope: str) -> None:
        cells_ref = scope_select_refs[scope]['cells'] = {}
        with ui.row().classes(
            'data-logger-header-grid w-full shrink-0 min-w-0 flex-nowrap '
            'overflow-x-auto overflow-y-hidden items-center pb-1 !pt-0'
        ):
            for prefix_label in ('realtime', 'step', 'sim_min'):
                with ui.element('div').classes(
                    'data-logger-header-cell data-logger-header-cell-readonly'
                ):
                    dot = ui.element('span').classes('data-logger-cell-color-dot')
                    dot.props(
                        'style="background-color: #ffd54f; opacity: 1; '
                        'box-shadow: 0 0 4px #ffd54f; "'
                    )
                    with ui.column().classes('data-logger-header-cell-text'):
                        ui.label(prefix_label).classes('data-logger-header-cell-tag')
                        ui.label('fixed').classes('data-logger-header-cell-meta')

            scoped = _split_fields_by_scope(list(bridge.state.available_log_fields)).get(scope, [])
            options = _order_fields_for_scope(scoped, loop_order, loop_signal_map)
            active_in_order = state.all_selected()
            color_by_field = {
                field_name: hub.get_field_color(field_name, active_in_order)
                for field_name in active_in_order
            }
            active = set(active_in_order)

            if not options:
                ui.label('(no fields available for this scope)').classes(
                    'data-logger-header-grid-empty'
                )
                return

            for field_name in options:
                _, _, tag = field_name.partition(':')
                is_active = field_name in active
                cell_color = color_by_field.get(field_name, '')
                unit = hub.registry.get_unit_for(field_name)
                display_tag = get_label(field_name, tag.upper())

                cell = ui.element('div').classes(
                    'data-logger-header-cell '
                    + (
                        'data-logger-header-cell-active'
                        if is_active
                        else 'data-logger-header-cell-inactive'
                    )
                )
                if is_active and cell_color:
                    cell.props(
                        f'style="border: 1px solid {cell_color} '
                        f'!important; '
                        f'background-color: {cell_color}26 '
                        f'!important; '
                        f'box-shadow: inset 0 0 0 1px '
                        f'{cell_color}55, 0 '
                        '0 6px -2px {cell_color}aa; "'
                    )
                with cell:
                    dot = ui.element('span').classes('data-logger-cell-color-dot')
                    if is_active and cell_color:
                        dot.props(
                            f'style="background-color: {cell_color}; '
                            'box-shadow: 0 0 4px {cell_color}; "'
                        )
                    else:
                        dot.props(
                            'style="background-color: #ffffff; opacity: 0.3; box-shadow: none; "'
                        )
                    with ui.column().classes('data-logger-header-cell-text'):
                        ui.label(display_tag).classes('data-logger-header-cell-tag')
                        ui.label(unit or '·').classes('data-logger-header-cell-meta')

                cell.on(
                    'click.stop',
                    lambda _event, f=field_name: state.toggle_field(f),
                )

                def _make_dblclick_handler(fn=field_name, c=cell):
                    return lambda e: open_rename_dialog(
                        fn,
                        get_label(fn, fn.partition(':')[2].upper()),
                        on_confirm=lambda: _on_cell_renamed(fn, c),
                    )

                cell.on('dblclick', _make_dblclick_handler())
                cells_ref[field_name] = cell

    with ui.column().classes('w-full flex-1 min-h-0 flex-nowrap overflow-hidden gap-0'):
        card_style = 'padding: 0 !important; gap: 0 !important;'
        if is_popout:
            card_style += ' border-radius: 0 !important; '
            card_style += 'border: none !important; '
            'margin: 0 !important; box-shadow: none !important;'
        with (
            ui.card()
            .classes(
                'data-logger-unified-panel w-full flex-1 min-h-0 flex flex-col overflow-hidden'
            )
            .props(f'style="{card_style}"')
        ):
            if show_header:
                with ui.row().classes('data-logger-page-title-row'):
                    with ui.column().classes('gap-1'):
                        ui.label('Data Logger').classes('data-logger-page-title')
                        ui.label('Live signals · use tabs below to select signals').classes(
                            'data-logger-page-subtitle'
                        )
                    with ui.row().classes('data-logger-page-actions'):
                        ui.button(
                            'All inputs',
                            on_click=lambda: state.toggle_all_for_scope('input'),
                            color=None,
                        ).props('flat no-caps dense').classes('data-logger-action-btn')
                        ui.button(
                            'All states',
                            on_click=lambda: state.toggle_all_for_scope('state'),
                            color=None,
                        ).props('flat no-caps dense').classes('data-logger-action-btn')
                        ui.button(
                            'All outputs',
                            on_click=lambda: state.toggle_all_for_scope('output'),
                            color=None,
                        ).props('flat no-caps dense').classes('data-logger-action-btn')
                        ui.button(
                            'Clear log',
                            on_click=state.clear_all_logs,
                            color=None,
                        ).props('flat no-caps dense').classes(
                            'data-logger-action-btn data-logger-action-btn-danger'
                        )
                        with (
                            ui.button('Save', color=None)
                            .props('flat no-caps dense icon-right=expand_more')
                            .classes('data-logger-action-btn data-logger-save-btn')
                        ):
                            with ui.menu().classes('data-logger-save-menu'):
                                ui.menu_item(
                                    'All scopes  →  CSV',
                                    lambda: _save_scope_as(None, 'csv'),
                                )
                                ui.menu_item(
                                    'All scopes  →  JSON',
                                    lambda: _save_scope_as(None, 'json'),
                                )
                                ui.separator()
                                for scope_key in _SCOPE_ORDER:
                                    ui.menu_item(
                                        f'{_SCOPE_TITLES[scope_key].title()} only  →  CSV',
                                        lambda _, s=scope_key: _save_scope_as(s, 'csv'),
                                    )
                                    ui.menu_item(
                                        f'{_SCOPE_TITLES[scope_key].title()} only  →  JSON',
                                        lambda _, s=scope_key: _save_scope_as(s, 'json'),
                                    )
                        if popout_url:
                            from app.components.popout_button import (
                                render_popout_button,
                            )

                            render_popout_button(
                                popout_url,
                                tooltip='Open Data Logger in new tab',
                            )

            with ui.column().classes('w-full shrink-0 gap-0'):
                with (
                    ui.tabs()
                    .classes('w-full text-[#ffd600]')
                    .props('dense align="justify" indicator-color="amber"') as tabs
                ):
                    tabs_ref['el'] = tabs
                    for scope in _SCOPE_ORDER:
                        tab_refs[scope] = ui.tab(name=scope, label=_SCOPE_TITLES[scope]).classes(
                            'text-[11px] font-bold tracking-wider uppercase'
                        )

                ui.separator().classes('data-logger-separator opacity-50')

                from nicegui import app

                tab_storage_key = (
                    f'data_logger_tab_{case_slug}_{popout_id}'
                    if (is_popout and popout_id)
                    else f'data_logger_tab_{case_slug}'
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
                    for scope in _SCOPE_ORDER:
                        with ui.tab_panel(tab_refs[scope]).classes('w-full p-2'):
                            header_container = ui.element('div').classes(
                                'data-logger-header-container'
                            )
                            scope_select_refs[scope]['grid_container'] = header_container
                            with header_container:
                                _build_header_grid(scope)

                ui.separator().classes('data-logger-separator opacity-50')
            # The optimal CSS approach to make QTable scroll within a
            # flex container
            # 1. The wrapper (probe) must be a flex column (flex-col).
            # 2. The table container itself must be a flex child that can
            # shrink (flex-1 min-h-0).
            INFO_HEIGHT = 120
            probe = ui.element('div').classes(
                'w-full flex-1 min-h-0 flex flex-col relative-position'
            )
            with probe:
                # Main data table — uses flex-1 min-h-0 to perfectly fill the
                # probe container
                table = (
                    ui.table(columns=[], rows=[], row_key='id', pagination=None)
                    .classes(
                        'data-logger-grid data-logger-grid-unified '
                        'border-none m-0 p-0 flex-1 min-h-0'
                    )
                    .props('dense flat wrap-cells=false')
                )
                unified_log_ref['log'] = table
                ui.run_javascript(f"""
                    setTimeout(() => {{
                        try {{
                            const comp = getElement({table.id});
                            if (!comp) return;
                            const el = comp.$el.querySelector(
                                '.q-table__middle'
                            );
                            if (!el) return;
                            el.scrollTop = el.scrollHeight;
                            let isAtBottom = true;
                            el.addEventListener('scroll', () => {{
                                isAtBottom = Math.abs(
                                    el.scrollHeight - el.scrollTop
                                    - el.clientHeight
                                ) < 50;
                            }}, {{ passive: true }});
                            const tbody = el.querySelector('tbody');
                            if (!tbody) return;
                            const observer = new MutationObserver(() => {{
                                if (isAtBottom) {{
                                    el.scrollTop = el.scrollHeight; }}
                            }});
                            observer.observe(tbody, {{ childList: true }});
                        }} catch(e) {{}}
                    }}, 500);
                """)

            # INFO — fixed height panel anchored to the bottom
            with (
                ui.column()
                .classes('w-full shrink-0 gap-0')
                .style(
                    f'height: {INFO_HEIGHT}px; display: flex; '
                    'flex-direction: column; '
                    f'background: rgba(0,0,0,0.6); overflow: hidden; '
                    f'border-top: 1px solid rgba(255,255,255,0.1);'
                )
            ):
                with (
                    ui.row()
                    .classes('w-full items-center justify-between p-2 pb-1 shrink-0')
                    .style('border-bottom: 1px solid rgba(255,255,255,0.1);')
                ):
                    ui.label('INFO').classes(
                        'text-[11px] font-bold tracking-wider uppercase text-[#ffd600]'
                    )
                    ui.label('Run / Stop / Reset, mode changes, status messages').classes(
                        'text-[10px] text-white/50'
                    )
                info_log = (
                    ui.log(max_lines=200)
                    .classes(
                        'w-full flex-1 data-logger-log data-logger-info-log '
                        'border-none rounded-none m-0 p-2'
                    )
                    .style(
                        'max-height: none !important; min-height: 0 '
                        '!important; overflow-y: auto !important;'
                    )
                )
                info_log_ref['log'] = info_log

                # Populate history from audit_log
                try:
                    history = app.storage.user.get(f'audit_log_{case_slug}') or []
                    counter = app.storage.user.get(f'audit_log_counter_{case_slug}', 0)
                    for line in history:
                        info_log.push(line)
                    state.last_seen_audit_counter = counter
                except Exception:
                    pass

            # Removed MutationObservers - auto-scroll is handled directly in
            # push_rows and replay_scopes

        _replay_scopes(None)
        state.start_flush_timer()


def write_audit_log(case_slug: str, message: str, bridge: Any = None) -> None:
    try:
        from datetime import datetime

        from nicegui import app

        history = app.storage.user.setdefault(f'audit_log_{case_slug}', [])
        counter = app.storage.user.setdefault(f'audit_log_counter_{case_slug}', 0)

        stamp = datetime.now().strftime('%H:%M:%S')
        sim_time = -1.0
        if bridge is not None:
            try:
                sim_time = float(getattr(bridge.state, 'global_sim_time', -1.0) or -1.0)
            except Exception:
                pass

        sim_str = f' (sim_min={sim_time:.1f})' if sim_time >= 0 else ''
        line = f'{stamp}{sim_str} | {message}'
        history.append(line)
        if len(history) > 200:
            history.pop(0)

        app.storage.user[f'audit_log_{case_slug}'] = history
        app.storage.user[f'audit_log_counter_{case_slug}'] = counter + 1
    except Exception:
        pass
