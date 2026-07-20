# app/main.py

"""ChemPlant Dynamics — NiceGUI entrypoint."""

import asyncio
import importlib
import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from fastapi import Response  # noqa: E402
from nicegui import app as nicegui_app  # noqa: E402
from nicegui import ui  # noqa: E402

from app.config import STATIC_DIR  # noqa: E402

importlib.import_module('app.pages.home_page')
importlib.import_module('app.pages.control_panel_page')
importlib.import_module('app.pages.popout_pages')

nicegui_app.add_static_files('/static', str(STATIC_DIR))


# ── Health-check endpoint ─────────────────────────────────────────────────────
# A lightweight route used by Docker HEALTHCHECK and container orchestrators.
# Returns 200 OK so liveness probes succeed without loading the full UI.
@nicegui_app.get('/health')
def health_check() -> Response:
    return Response(content='ok', media_type='text/plain')


ui.run(
    title='ChemPlant Dynamics',
    dark=True,
    host='0.0.0.0',
    port=8080,
    # NiceGUI deployment recommendations:
    #   show=False  → don't try to open a browser (headless server/container).
    #   reload=False → disable the file-watcher; not needed (and wastes CPU) in production.
    show=False,
    reload=False,
    storage_secret=os.environ.get('STORAGE_SECRET', 'chemplant-dev-secret-change-me'),
)
