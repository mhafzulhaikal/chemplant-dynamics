# app/hub/__init__.py

"""Parent–child broadcast hub.

A small, single-producer / multi-subscriber layer that sits between the
engine bridge and the per-page UI children (SVG, faceplate, modal). One
``ui.timer`` in :class:`SignalHub` drains the bridge each tick, folds
the records into a snapshot, and notifies every attached child — so
every child sees the same value in the same tick.

See ``README.md`` (section "Architecture — Parent–Child Broadcast Hub")
and ``signal_hub.py`` for the full picture.
"""

from app.hub.controller_registry import ControllerRegistry, ControllerSpec
from app.hub.engine_control import EngineControl
from app.hub.signal_hub import SignalHub, Subscriber, TickMeta

__all__ = [
    'ControllerRegistry',
    'ControllerSpec',
    'EngineControl',
    'Subscriber',
    'SignalHub',
    'TickMeta',
]
