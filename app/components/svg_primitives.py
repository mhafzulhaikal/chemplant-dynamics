# app/components/svg_primitives.py

"""Shared SVG primitives used by every case's P&ID drawing.

Both ``app.components.sthr_component`` (STHR) and
``app.components.biodiesel_component`` (biodiesel) need the same
:mod:`drawsvg` scaffolding: a ``Port`` dataclass, an ``Equipment`` base
class, and a small helper for building linear gradients. They used to
duplicate this scaffolding — having one copy here means a single point
of truth for the SVG equipment hierarchy.

Pure UI: no engine, no gateway, no case-specific config. Anything
imported from this module must stay drawsvg-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import drawsvg as draw


@dataclass
class Port:
    """A named connection point on a piece of equipment.

    Coordinates are local to the equipment's own transform group;
    :meth:`Equipment.port_abs` converts them to absolute SVG
    coordinates.
    """

    x: float
    y: float


@dataclass
class Equipment:
    """Base class for every drawable piece of P&ID equipment.

    Subclasses extend :meth:`render` to append their own ``draw.Group``
    children (gradients, paths, ports, …). The base class only owns the
    equipment's id, transform, port map, and a status flag used by the
    SVG CSS for fault-state colouring.
    """

    id: str
    x: float
    y: float
    ports: dict[str, Port] = field(default_factory=dict)
    status: str = 'normal'

    def port_abs(self, name: str) -> Port:
        """Resolve ``name`` to an absolute (x, y) point.

        Raises ``KeyError`` if the port name is not registered.
        """
        p = self.ports[name]
        return Port(self.x + p.x, self.y + p.y)


def metallic_gradient(
    grad_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    colors: Sequence[tuple[float, str]],
    units: str = 'userSpaceOnUse',
) -> draw.LinearGradient:
    """Build a metallic linear gradient with the given colour stops.

    The stop list is a sequence of ``(offset, color)`` pairs in the
    range ``0.0..1.0``. Centralised so the same chrome / copper / steel
    palettes can be reused across the STHR and biodiesel P&ID
    components.
    """
    lg = draw.LinearGradient(x1, y1, x2, y2, id=grad_id, gradientUnits=units)
    for offset, color in colors:
        lg.add_stop(offset, color)
    return lg


__all__ = ['Port', 'Equipment', 'metallic_gradient']
