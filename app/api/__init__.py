# app/api/__init__.py

"""FastAPI routers — mounted onto the production ASGI app in app/server.py."""

from app.api.health import health_router
from app.api.simulation import sim_router

__all__ = ['health_router', 'sim_router']
