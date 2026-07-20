# app/hub/children/modals/__init__.py

"""Controller-modal package.

Rewritten from the legacy ``app/pid/sthr/controller_modal.py`` +
``app/pid/biodiesel/controller_modal.py`` during the v1 purge.
Split into focused modules:

- :mod:`placement` — :data:`MANUAL_ANCHORS` + :class:`_SmartPlacementMixin`
  (per-tag corner placement with double-rAF retry).
- :mod:`base` — :class:`ControllerModal` (tunable dialog).
- :mod:`readonly` — :class:`ReadOnlyControllerModal` (indicator dialog).
- :mod:`sthr` — 7 STHR controller subclasses.
- :mod:`biodiesel` — :class:`ValvePositionModal` + 15 biodiesel subclasses.

The public API matches the legacy classes byte-for-byte (signatures,
attribute names, method semantics, status flags) so the view modules
in ``app/pid/<case>/view.py`` only had to change their import path —
no constructor or behaviour rewrite required.
"""

from app.hub.children.modals.base import ControllerModal
from app.hub.children.modals.biodiesel import (
    Fi100ControllerModal as Fi100BiodieselModal,
)
from app.hub.children.modals.biodiesel import (
    Fi101ControllerModal as Fi101BiodieselModal,
)
from app.hub.children.modals.biodiesel import (
    Fic100ControllerModal,
    Fic101ControllerModal,
    Fic102ControllerModal,
    Fv100ValvePositionModal,
    Fv101ValvePositionModal,
    Fv102ValvePositionModal,
    Lic100ControllerModal,
    Lv100ValvePositionModal,
    Pi100ControllerModal,
    Ti101ControllerModal,
    Ti102ControllerModal,
    Ti103ControllerModal,
    Ti104ControllerModal,
    Tv100ValvePositionModal,
    ValvePositionModal,
)
from app.hub.children.modals.biodiesel import (
    Ti100ControllerModal as Ti100BiodieselModal,
)
from app.hub.children.modals.biodiesel import (
    Tic100ControllerModal as Tic100BiodieselModal,
)
from app.hub.children.modals.readonly import ReadOnlyControllerModal
from app.hub.children.modals.sthr import (
    Fi100ControllerModal,
    Fi101ControllerModal,
    Fi102ControllerModal,
    Li100ControllerModal,
    Ti100ControllerModal,
    Tic100ControllerModal,
    Vp100ControllerModal,
)

__all__ = [
    'ControllerModal',
    'ReadOnlyControllerModal',
    'ValvePositionModal',
    # STHR
    'Tic100ControllerModal',
    'Fi100ControllerModal',
    'Fi101ControllerModal',
    'Ti100ControllerModal',
    'Li100ControllerModal',
    'Fi102ControllerModal',
    'Vp100ControllerModal',
    # Biodiesel (aliased on import to avoid name clash with STHR)
    'Lic100ControllerModal',
    'Tic100BiodieselModal',
    'Fic100ControllerModal',
    'Fic101ControllerModal',
    'Fic102ControllerModal',
    'Ti100BiodieselModal',
    'Ti101ControllerModal',
    'Ti102ControllerModal',
    'Ti103ControllerModal',
    'Ti104ControllerModal',
    'Fi100BiodieselModal',
    'Fi101BiodieselModal',
    'Pi100ControllerModal',
    'Lv100ValvePositionModal',
    'Tv100ValvePositionModal',
    'Fv100ValvePositionModal',
    'Fv101ValvePositionModal',
    'Fv102ValvePositionModal',
]
