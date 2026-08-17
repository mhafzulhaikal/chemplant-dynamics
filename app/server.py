# app/server.py

"""ChemPlant Dynamics — production ASGI entrypoint.

This module owns the FastAPI + uvicorn lifecycle.  NiceGUI is mounted
*into* the FastAPI app via ``ui.run_with()`` — the official NiceGUI
pattern for integrating with an existing ASGI app.

Architecture
------------
::

    uvicorn  ──►  FastAPI (this module)
                    │
                    ├── GET  /health         (app/api/health.py)
                    ├── GET  /api/v1/sim/*   (app/api/simulation.py)
                    ├── GET  /docs           (OpenAPI — free from FastAPI)
                    ├── /static/*            (Starlette StaticFiles)
                    │
                    └── NiceGUI (ui.run_with)
                          ├── /             home_page
                          ├── /control      control_panel_page
                          ├── /popout/*     popout_pages
                          └── /_nicegui/*   internal JS/CSS/WS

Usage
-----
Production (Docker / server)::

    uvicorn app.server:fastapi_app --host 0.0.0.0 --port 8080 --workers 1

Direct (python)::

    python app/server.py

Development with hot-reload (file-watcher)::

    python app/main.py          # still works — uses ui.run() directly

Notes
-----
* ``--workers 1`` is mandatory.  NiceGUI holds shared in-process state
  (SignalHub, Bridge queues).  Running multiple workers would create
  isolated copies of that state — pages on different workers would never
  see each other's data.  Scale horizontally only with a Redis-backed
  session store if multi-instance is ever needed.
* ``reload=False`` in ``ui.run_with`` — hot-reload is Uvicorn's job when
  you pass ``--reload`` to the CLI.  The NiceGUI file-watcher is not
  needed (and wastes CPU) in this setup.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from nicegui import ui

# ── Path bootstrap (mirrors app/main.py) ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Windows asyncio policy ─────────────────────────────────────────────────────
if sys.platform == 'win32' and sys.version_info < (3, 14):
    import asyncio

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError, RuntimeError:
        pass

from app.api import health_router, sim_router  # noqa: E402
from app.config import STATIC_DIR  # noqa: E402
from app.nicegui_patch import apply_windows_storage_patch  # noqa: E402

apply_windows_storage_patch()

logger = logging.getLogger(__name__)

# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """ASGI lifespan handler — startup and graceful shutdown.

    NiceGUI pages are imported here (not at module level) so that
    ``ui.run_with`` has already registered the NiceGUI middleware before
    any ``@ui.page`` decorator is executed.
    """
    logger.info('ChemPlant Dynamics: starting up…')

    importlib.import_module('app.pages.home_page')
    importlib.import_module('app.pages.control_panel_page')
    importlib.import_module('app.pages.popout_pages')

    logger.info('ChemPlant Dynamics: all pages registered — server ready.')
    yield

    logger.info('ChemPlant Dynamics: shutting down…')
    # Graceful bridge teardown can be added here if the Bridge
    # ever exposes a .close() / .shutdown() method.


# ── FastAPI app ────────────────────────────────────────────────────────────────

fastapi_app = FastAPI(
    title='ChemPlant Dynamics',
    description=(
        'REST API and real-time UI for chemical-plant process-control simulation.\n\n'
        'The UI is served by NiceGUI (mounted at `/`). '
        'REST endpoints live under `/api/v1/`.'
    ),
    version='0.1.0',
    lifespan=lifespan,
    # Keep docs at default /docs & /redoc paths.
)

# Static files (served by Starlette directly — slightly faster than NiceGUI's
# add_static_files wrapper because it uses Starlette's optimised StaticFiles
# middleware with proper Last-Modified / ETag / gzip headers).
fastapi_app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

# ── REST routers ───────────────────────────────────────────────────────────────

fastapi_app.include_router(health_router)
fastapi_app.include_router(sim_router, prefix='/api/v1')

# ── NiceGUI mount ──────────────────────────────────────────────────────────────
# ui.run_with() registers NiceGUI's ASGI middleware onto fastapi_app and
# returns immediately (uvicorn is *not* started here — that's our job below).
# Pages are imported in the lifespan handler above.

ui.run_with(
    fastapi_app,
    title='ChemPlant Dynamics',
    dark=True,
    reconnect_timeout=30,  # wait 30 s on network drop before hard-reloading
    storage_secret=os.environ.get('STORAGE_SECRET', 'chemplant-dev-secret-change-me'),
)

# ── Direct-run entrypoint ──────────────────────────────────────────────────────
# ``python app/server.py``  →  production-equivalent local launch
# (no file-watcher, no browser auto-open, controlled graceful shutdown).

if __name__ == '__main__':
    uvicorn.run(
        'app.server:fastapi_app',
        host='0.0.0.0',
        port=8080,
        workers=1,  # see module docstring — multi-worker is unsafe here
        reload=False,  # use `python app/main.py` for hot-reload dev mode
        log_level='info',
    )
