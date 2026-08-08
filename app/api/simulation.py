# app/api/simulation.py

"""Simulation status REST endpoints.

Provides a thin, read-only REST surface over the active simulation state.
All data is pulled directly from the global ``EngineControl`` exposed by
the SignalHub — no extra IPC, no duplication of bridge state.

Routes
------
GET /api/v1/sim/status   — current engine status, sim-time, step counter
GET /api/v1/sim/cases    — list of registered simulation cases

These endpoints are intentionally read-only.  Control actions (run/stop/
reset) remain UI-only for now — add POST routes here if you ever need a
headless control surface (CI integration, Jupyter, Grafana annotations, …).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

sim_router = APIRouter(prefix='/sim', tags=['Simulation'])


# ── Response models ────────────────────────────────────────────────────────────


class SimStatusResponse(BaseModel):
    """Real-time simulation state snapshot."""

    status: str = Field(..., description="Engine status: 'idle' | 'running' | 'paused' | 'error'")
    sim_time: float = Field(..., description='Simulation clock in minutes')
    step_index: int = Field(..., description='Total physics steps completed')
    controller_mode: str = Field(..., description="'Off' | 'Manual' | 'Automatic'")
    real_time: bool = Field(..., description='Whether real-time pacing is active')


class CaseInfo(BaseModel):
    name: str
    label: str


class CasesResponse(BaseModel):
    cases: list[CaseInfo]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_active_hub() -> object:
    """Retrieve the active SignalHub from NiceGUI app storage.

    SignalHub instances are stored in ``app.storage.general`` keyed by case
    name.  We look for the first running hub so the status endpoint works
    regardless of which case is active.

    Returns None if no hub has been initialised yet (app still loading).
    """
    try:
        from nicegui import app as nicegui_app

        storage = nicegui_app.storage.general  # type: ignore[attr-defined]
        hub = storage.get('_active_hub')
        return hub
    except Exception:
        return None


# ── Routes ─────────────────────────────────────────────────────────────────────


@sim_router.get(
    '/status',
    response_model=SimStatusResponse,
    summary='Current simulation status',
)
async def get_sim_status() -> SimStatusResponse:
    """Return the live simulation clock, step counter, and engine status.

    This endpoint reads directly from the in-process bridge state — it is
    as fresh as the last SignalHub tick (typically 100–250 ms cadence).
    """
    hub = _get_active_hub()

    if hub is None:
        # App still initialising or no case loaded yet.
        raise HTTPException(
            status_code=503,
            detail='No active simulation hub — app may still be loading.',
        )

    try:
        ec = hub.engine_control  # type: ignore[attr-defined]
        return SimStatusResponse(
            status=str(ec.status or 'idle'),
            sim_time=float(ec.sim_time or 0.0),
            step_index=int(getattr(ec, '_adapter', ec).drain_one()[1].step_index if hasattr(ec, '_adapter') else -1),
            controller_mode=str(ec.controller_mode or 'Automatic'),
            real_time=bool(ec.real_time),
        )
    except Exception as exc:
        logger.warning('sim/status: failed to read engine state — %s', exc)
        raise HTTPException(status_code=500, detail='Failed to read simulation state.') from exc


@sim_router.get(
    '/cases',
    response_model=CasesResponse,
    summary='Available simulation cases',
)
async def get_cases() -> CasesResponse:
    """List all registered simulation cases (e.g. STHR, Biodiesel)."""
    try:
        from engine.case_registry import CaseRegistry  # type: ignore[import]

        registry = CaseRegistry()
        cases = [CaseInfo(name=k, label=v) for k, v in registry.list_cases().items()]
    except Exception:
        # If case registry isn't available, return a static fallback.
        cases = [
            CaseInfo(name='sthr', label='Steam-Tube Heat Reactor (STHR)'),
            CaseInfo(name='biodiesel', label='Biodiesel Transesterification'),
        ]
    return CasesResponse(cases=cases)
