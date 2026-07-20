# gateway/adapters/biodiesel_bridge.py

"""Biodiesel-specific gateway bridge entry point.

This module is the biodiesel-side counterpart of :mod:`gateway.bridge`
and the case-specific re-export of the case-agnostic :class:`Bridge`
class. The underlying implementation is shared between every case —
it accepts a ``case_name`` argument and dispatches to the matching
``cases.<name>.config`` module via
:func:`gateway.registry.config_registry.get_case_config`.

The class is re-exported under the case-specific name
``BiodieselBridge`` so the biodiesel code path can import a class
whose name matches the case it serves. This mirrors the project
layout convention where every case ships its own ``*_bridge.py``
alongside ``*_bridge_store.py`` and ``*_engine_bootstrap.py``.

New code should prefer importing from :mod:`gateway.bridge`
(``from gateway.bridge import Bridge``) — the ``case_name='biodiesel'``
argument is what actually wires the bridge to the biodiesel case.
"""

from __future__ import annotations

from gateway.bridge import Bridge

# Case-specific alias. Mirrors the historical STHR-named
# ``STHRBridge`` import path so the biodiesel code path can write
# ``from gateway.adapters.biodiesel_bridge import BiodieselBridge`` for
# symmetry. The class itself is shared with every other case.
BiodieselBridge = Bridge


__all__ = ['BiodieselBridge']
