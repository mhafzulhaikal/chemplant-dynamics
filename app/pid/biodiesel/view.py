# app/pid/biodiesel/view.py

"""Biodiesel P&ID view.

Wraps :func:`app.biodiesel_drawing.build_biodiesel_drawing` and wires
 the controller modals to a hub-backed store adapter
(:class:`HubStoreAdapter`) so each modal's existing ``store.get`` /
``store.set`` calls route through :meth:`SignalHub.request_write`
on the way down and :meth:`SignalHub.snapshot` on the way back up.
"""

from __future__ import annotations

from app.biodiesel_drawing import build_biodiesel_drawing
from app.hub.children.modal_child import HubStoreAdapter
from app.hub.children.modals import (
    Fi100BiodieselModal,
    Fi101BiodieselModal,
    Fic100ControllerModal,
    Fic101ControllerModal,
    Fic102ControllerModal,
    Fv100ValvePositionModal,
    Fv101ValvePositionModal,
    Fv102ValvePositionModal,
    Lic100ControllerModal,
    Lv100ValvePositionModal,
    Pi100ControllerModal,
    ReadOnlyControllerModal,
    Ti100BiodieselModal,
    Ti101ControllerModal,
    Ti102ControllerModal,
    Ti103ControllerModal,
    Ti104ControllerModal,
    Tic100BiodieselModal,
    Tv100ValvePositionModal,
)
from app.hub.children.svg_vue_child import SvgVueChild
from app.hub.signal_hub import SignalHub


def render_biodiesel_pid_svg(hub: SignalHub):
    """Render the biodiesel P&ID and wire the controller modals to ``hub``.

    Returns the ``ui.html`` element; ``html_element.controller_modals``
    is set on it (same protocol the faceplate / modal child expect) so
    :class:`ModalChild` and :class:`FaceplateChild` can pull it out of
    the page directly.
    """
    from typing import Any

    store: Any = HubStoreAdapter(hub)
    html_element = SvgVueChild(build_biodiesel_drawing(), classes='svg-full biodiesel-pid-svg')

    tunable_modals: dict[str, Any] = {
        'lic-100': Lic100ControllerModal(store, html_element),
        'tic-100': Tic100BiodieselModal(store, html_element),
        'fic-100': Fic100ControllerModal(store, html_element),
        'fic-101': Fic101ControllerModal(store, html_element),
        'fic-102': Fic102ControllerModal(store, html_element),
        'ti-100': Ti100BiodieselModal(store, html_element),
        'ti-101': Ti101ControllerModal(store, html_element),
        'ti-102': Ti102ControllerModal(store, html_element),
        'ti-103': Ti103ControllerModal(store, html_element),
    }
    readonly_modals: dict[str, ReadOnlyControllerModal] = {
        'ti-104': Ti104ControllerModal(store, html_element),
        'fi-100': Fi100BiodieselModal(store, html_element),
        'fi-101': Fi101BiodieselModal(store, html_element),
        'pi-100': Pi100ControllerModal(store, html_element),
        'lv-100': Lv100ValvePositionModal(store, html_element),
        'tv-100': Tv100ValvePositionModal(store, html_element),
        'fv-100': Fv100ValvePositionModal(store, html_element),
        'fv-101': Fv101ValvePositionModal(store, html_element),
        'fv-102': Fv102ValvePositionModal(store, html_element),
    }
    all_modals: dict[str, object] = {}
    all_modals.update(tunable_modals)
    all_modals.update(readonly_modals)
    html_element.controller_modals = all_modals  # type: ignore

    for spec in hub.registry.svg_emitters():
        if spec.svg_id:
            html_element.add_computed(
                spec.svg_id,
                lambda snap, mk=spec.modal_key: hub.registry.format(mk, snap.get(mk, 0.0)),
            )

    for spec in hub.registry:
        if spec.role == 'sp':
            html_element.add_computed(
                spec.modal_key,
                lambda snap, mk=spec.modal_key: hub.registry.format(mk, snap.get(mk, 0.0)),
            )

    html_element.add_computed(
        'reactor_cylinder_fill',
        lambda snap: (
            '#FF0000'
            if float(snap.get('tic_pv', 0.0)) > 360.0
            else (
                '#FFC000'
                if float(snap.get('tic_pv', 0.0)) > 348.0
                else 'url(#gradient_reactor_cylinder)'
            )
        ),
    )
    html_element.add_computed(
        'reactor_fluid_scale', lambda snap: max(0.0, min(1.0, float(snap.get('lic_pv', 0.0)) / 3.0))
    )
    html_element.add_computed(
        'upper_blade_submerged', lambda snap: float(snap.get('lic_pv', 0.0)) >= 2.3
    )

    if hasattr(hub, 'ui_sync'):
        hub.ui_sync.register_class_toggle(
            html_element,
            'pid-animation-running',
            lambda: getattr(hub.bridge.state, 'status', 'idle') in ('running', 'starting'),
        )

    html_element.initial_sync(hub)
    hub.subscribe(html_element)

    return html_element


__all__ = ['render_biodiesel_pid_svg']
