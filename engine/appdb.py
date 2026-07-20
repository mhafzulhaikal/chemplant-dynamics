# engine/appdb.py

"""AppDB — the in-memory historian used by every case.

This module is intentionally case-agnostic. Each AppDB instance manages its
own timeseries and backend configuration, ensuring complete isolation across
different cases, tabs, and sessions.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Iterable, Mapping
from typing import Any


class _CsvTimeseriesBackend:
    def __init__(self, path: str):
        self.path = path
        # ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # write header if file empty
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, 'a', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['plant_id', 'tag', 't', 'value'])

    def append(self, record: dict) -> None:
        with open(self.path, 'a', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(
                [
                    record.get('plant_id'),
                    record.get('tag'),
                    record.get('t'),
                    record.get('value'),
                ]
            )

    def extend(self, records: Iterable[dict]) -> None:
        with open(self.path, 'a', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            for r in records:
                writer.writerow([r.get('plant_id'), r.get('tag'), r.get('t'), r.get('value')])


class _MemoryBackend:
    def append(self, record: dict) -> None:
        pass

    def extend(self, records: Iterable[dict]) -> None:
        pass


class AppDB:
    def __init__(self, backend_params: Mapping[str, Any] | None = None):
        # --- TAG SYSTEM ---
        self.tags: dict[str, object] = {}  # tag_name -> Tag

        # --- SESSION ---
        # session_id -> SimulationSession
        self.sessions: dict[str, object] = {}

        # --- HISTORIAN ---
        self.timeseries: list[dict] = []  # list of dict (time-series data)

        # --- BACKEND ---
        params = backend_params or {}
        backend_type = str(params.get('timeseries_backend', 'memory')).lower()
        if backend_type == 'csv':
            path = params.get('timeseries_csv_path', './timeseries.csv')
            try:
                self.backend = _CsvTimeseriesBackend(path)
            except Exception:
                self.backend = _MemoryBackend()
        else:
            self.backend = _MemoryBackend()


# global singleton (kept for backward compatibility with older
# tests/scripts that import default_appdb)
appdb = AppDB()


def set_active_case_config(simulation_params: Mapping[str, Any] | None) -> None:
    """Legacy shim — does nothing.

    AppDB instances now take params in __init__.
    """
    pass


def log_timeseries(
    appdb_instance: AppDB, plant_id: Any, tag_name: str, t: float, value: float
) -> None:
    record = {'plant_id': plant_id, 'tag': tag_name, 't': t, 'value': value}
    try:
        appdb_instance.backend.append(record)
    except Exception:
        pass

    try:
        appdb_instance.timeseries.append(record)
    except Exception:
        pass


def append_timeseries_records(appdb_instance: AppDB, records: Iterable[dict]) -> None:
    """Append an iterable of timeseries records using the configured backend.

    On success: writes via backend and mirrors to ``appdb.timeseries``.
    On failure: writes to ``appdb.timeseries`` only (no double-write).
    """
    recs = list(records)
    backend_ok = False
    try:
        appdb_instance.backend.extend(recs)
        backend_ok = True
    except Exception:
        pass

    if not backend_ok:
        # Backend failed — write to in-memory list only.
        for r in recs:
            try:
                appdb_instance.timeseries.append(r)
            except Exception:
                continue
        return

    # Mirror into in-memory list for tests/compat.
    try:
        appdb_instance.timeseries.extend(recs)
    except Exception:
        for r in recs:
            try:
                appdb_instance.timeseries.append(r)
            except Exception:
                continue


def add_tag(appdb_instance: AppDB, tag: Any) -> None:
    appdb_instance.tags[tag.name] = tag
