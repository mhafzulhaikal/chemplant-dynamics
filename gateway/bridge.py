# gateway/bridge.py

"""Public gateway bridge facade.

This module is the single entry point every case (STHR, biodiesel,
and any future case) should use to obtain a bridge instance. The
implementation lives in :mod:`gateway.core.bridge_class`; the support
types (:class:`BridgeState`, :class:`BridgeRecord`, :func:`safe_float`)
live in :mod:`gateway.core.bridge_support`.

The :class:`Bridge` class is case-agnostic — it dispatches to the
right ``cases.<name>.config`` module based on the ``case_name``
argument passed to ``__init__``. Both STHR and biodiesel code paths
construct a :class:`Bridge` with their respective ``case_name``;
the only difference is the dispatch key.
"""

from __future__ import annotations

from gateway.core.bridge_class import Bridge
from gateway.core.bridge_support import (
    BridgeRecord,
    BridgeState,
    safe_float,
)

__all__ = [
    'Bridge',
    'BridgeState',
    'BridgeRecord',
    'safe_float',
]
