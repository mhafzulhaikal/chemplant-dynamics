# app/main.py

"""ChemPlant Dynamics — DEVELOPMENT entrypoint (hot-reload, browser auto-open).

This file is intentionally kept as a lightweight dev shortcut that boots
NiceGUI with its built-in file-watcher and browser opener.

**For production / Docker use ``app/server.py`` instead.**

Comparison
----------
* ``python app/main.py``        — dev mode (reload=True, show=True)
* ``python app/server.py``      — production (uvicorn, no reload)
* ``uvicorn app.server:fastapi_app ...``  — same as above, explicit
"""

import asyncio
import importlib
import os
import sys
from pathlib import Path

if sys.platform == 'win32' and sys.version_info < (3, 14):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except (AttributeError, RuntimeError):
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from nicegui import app as nicegui_app  # noqa: E402
from nicegui import ui  # noqa: E402

from app.config import STATIC_DIR  # noqa: E402

importlib.import_module('app.pages.home_page')
importlib.import_module('app.pages.control_panel_page')
importlib.import_module('app.pages.popout_pages')

nicegui_app.add_static_files('/static', str(STATIC_DIR))

# ── Dev-only health check ─────────────────────────────────────────────────────
# In production (app/server.py) the health route is registered as a proper
# FastAPI router (app/api/health.py).  We keep a minimal version here so
# `python app/main.py` still responds to /health during local dev.
from fastapi import Response  # noqa: E402


@nicegui_app.get('/health')
def health_check() -> Response:
    return Response(content='ok', media_type='text/plain')


# ── Dev server ───────────────────────────────────────────────────────────────
# reload=True  → NiceGUI file-watcher restarts on source changes (dev only)
# show=True    → auto-opens browser tab (dev only)
# For production use app/server.py with uvicorn instead.
ui.run(
    title='ChemPlant Dynamics',
    dark=True,
    host='0.0.0.0',
    port=8080,
    show=True,
    reload=True,
    storage_secret=os.environ.get('STORAGE_SECRET', 'chemplant-dev-secret-change-me'),
)
