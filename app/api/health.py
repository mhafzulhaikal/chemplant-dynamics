# app/api/health.py

"""Lightweight liveness / readiness endpoint.

Replaces the ad-hoc ``@nicegui_app.get('/health')`` that lived in
``app/main.py``.  Same semantics: returns HTTP 200 plain-text ``ok``
so Docker HEALTHCHECK, container orchestrators, and load-balancer
probes all pass without loading the full UI.
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

health_router = APIRouter(tags=['Health'])


@health_router.get(
    '/health',
    response_class=PlainTextResponse,
    summary='Liveness probe',
    description='Returns 200 OK when the server is up. Used by Docker HEALTHCHECK.',
)
async def health_check() -> str:
    return 'ok'
