# app/pid/sthr/view.py

"""STHR P&ID view.

Wraps :func:`app.sthr_drawing.build_sthr_drawing` and wires the
controller modals to a hub-backed store adapter
(:class:`HubStoreAdapter`) so each modal's existing ``store.get`` /
``store.set`` calls route through :meth:`SignalHub.request_write` on the
way down and :meth:`SignalHub.snapshot` on the way back up.
"""

from __future__ import annotations

from app.hub.children.modal_child import HubStoreAdapter
from app.hub.children.modals import (
    Fi100ControllerModal,
    Fi101ControllerModal,
    Fi102ControllerModal,
    Li100ControllerModal,
    Ti100ControllerModal,
    Tic100ControllerModal,
    Vp100ControllerModal,
)
from app.hub.children.svg_vue_child import SvgVueChild
from app.hub.signal_hub import SignalHub
from app.sthr_drawing import build_sthr_drawing


def render_sthr_pid_svg(hub: SignalHub):
    """Render the STHR P&ID and wire the controller modals to ``hub``.

    Returns the ``ui.html`` element; ``html_element.controller_modals``
    is set on it (same protocol the faceplate / modal child expect) so
    :class:`ModalChild` and :class:`FaceplateChild` can pull it out of
    the page directly.
    """
    from typing import Any

    store: Any = HubStoreAdapter(hub)
    html_element = SvgVueChild(build_sthr_drawing(), classes='svg-full sthr-pid-svg')

    tunable_modals: dict[str, Any] = {
        'tic-100': Tic100ControllerModal(store, html_element),
        'fi-101': Fi101ControllerModal(store, html_element),
        'ti-100': Ti100ControllerModal(store, html_element),
    }
    readonly_modals: dict[str, Any] = {
        'fi-100': Fi100ControllerModal(store, html_element),
        'li-100': Li100ControllerModal(store, html_element),
        'fi-102': Fi102ControllerModal(store, html_element),
        'vp-100': Vp100ControllerModal(store, html_element),
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
            if float(snap.get('pv', 0.0)) > 360.0
            else (
                '#FFC000'
                if float(snap.get('pv', 0.0)) > 348.0
                else 'url(#gradient_reactor_cylinder)'
            )
        ),
    )
    html_element.add_computed(
        'reactor_fluid_scale',
        lambda snap: max(0.0, min(1.0, float(snap.get('li100_pv', 0.0)) / 200.0)),
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


__all__ = ['render_sthr_pid_svg']
