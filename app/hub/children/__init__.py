# app/hub/children/__init__.py

"""Built-in children for :class:`app.hub.SignalHub`.

Each child is a thin :class:`Subscriber` implementing ``on_tick``.
Children NEVER call ``bridge.drain_records()`` themselves — the hub is
the single drain point. Each child exposes a small ``control`` object
for child-local actions (toggles, selection, open/close) that do NOT
need to round-trip through the hub or the engine.

Data Logger and Performance Monitor are NOT children in this sense —
they are page-level renderers (``app/hub/data_logger.py``,
``app/hub/perf_monitor.py``) that consume ``hub.engine_control.bridge``
directly. They were ports of the original v1 modules and kept their own
``ui.timer`` polling so the column-picker / export / replay behavior
stays identical.
"""

from app.hub.children.faceplate_child import FaceplateChild
from app.hub.children.modal_child import ModalChild
from app.hub.children.svg_vue_child import SvgVueChild

__all__ = [
    'FaceplateChild',
    'ModalChild',
    'SvgVueChild',
]
