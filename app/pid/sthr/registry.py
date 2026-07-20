# app/pid/sthr/registry.py

"""STHR :class:`ControllerRegistry` — single source of truth.

This module encodes every controller-side mapping the STHR P&ID
needs as one flat list of :class:`ControllerSpec`. It is the only
place a unit, decimal, modal_key, or engine_tag is defined — every
child (SVG, faceplate, modal, data logger, perf monitor) reads
from this same registry.

Indexed views consumed by the hub:

- ``output_to_pv()``  — engine tag → modal key (drives PV update).
- ``input_field_to_override()`` — modal key → engine tag (drives write).
- ``status_keys()``   — keys routed through ``apply_runtime_configuration``.
- ``svg_emitters()``  — specs with an ``svg_id`` (drive the SVG <text>).
- ``derived_pairs()`` — copies for indicators without their own tag.
"""

from __future__ import annotations

from app.hub.controller_registry import ControllerRegistry, ControllerSpec

# ── Spec list ──────────────────────────────────────────────────────
# Convention:
#  - PV specs reference the engine OUTPUT tag (``STHR.T``,
#    ``TV-100.F``, …) and carry the SVG card id so the SvgChild
#    can write into ``<text id="<svg_id>-value">``.
#  - SP / OP / tuning specs reference the engine INPUT tag
#    (``TSP-100.SP``, ``TV-100.M``, ``TC-100.Kc``, …) and are
#    ``writable=True``.
#  - Status specs (``tic_status``) carry no engine tag — the hub
#    routes them through ``apply_runtime_configuration``.
#  - Dual-purpose ``op``: declared AFTER the read-only PV spec for
#    ``TC-100.M`` so the writable entry wins in the engine-tag
#    index (matches the legacy ``BaseBridgeStore.set`` rule
#    "input override wins").

_SPECS: list[ControllerSpec] = [
    # ── TIC-100 (Temperature Controller, the only PID loop) ──
    ControllerSpec(
        modal_key='pv',
        engine_tag='STHR.T',
        svg_id='tic-100',
        unit='°F',
        decimals=1,
        role='pv',
        writable=False,
        range=(100.0, 200.0),
        title='Temperature Controller',
    ),
    ControllerSpec(
        modal_key='sp',
        engine_tag='TSP-100.SP',
        svg_id=None,
        unit='°F',
        decimals=1,
        role='sp',
        writable=True,
        range=(100.0, 200.0),
    ),
    # Read-only output projection (TC-100.M → 'op') — declared first
    # so the writable spec below overwrites the engine-tag index.
    ControllerSpec(
        modal_key='op_readback',
        engine_tag='TC-100.M',
        svg_id=None,
        unit='%CO',
        decimals=1,
        role='op',
        writable=False,
        range=(0.0, 100.0),
    ),
    # Writable MV (manual mode) — both legacy paths map 'op' to
    # this tag so we keep the same modal key.
    ControllerSpec(
        modal_key='op',
        engine_tag='TV-100.M',
        svg_id=None,
        unit='%CO',
        decimals=1,
        role='op',
        writable=True,
        range=(0.0, 100.0),
        derived_from='op_readback',
    ),
    ControllerSpec(
        modal_key='kc',
        engine_tag='TC-100.Kc',
        svg_id=None,
        unit='%CO/%TO',
        decimals=2,
        role='tuning',
        writable=True,
        range=(0.0, 50.0),
    ),
    ControllerSpec(
        modal_key='tau_i',
        engine_tag='TC-100.tauI',
        svg_id=None,
        unit='min',
        decimals=2,
        role='tuning',
        writable=True,
        range=(0.01, 100.0),
    ),
    ControllerSpec(
        modal_key='tau_d',
        engine_tag='TC-100.tauD',
        svg_id=None,
        unit='min',
        decimals=2,
        role='tuning',
        writable=True,
        range=(0.0, 50.0),
    ),
    ControllerSpec(
        modal_key='tic_status',
        engine_tag=None,
        svg_id=None,
        unit='',
        decimals=0,
        role='status',
        writable=True,
    ),
    # ── Indicators (read-only PV + SVG card) ─────────────────────
    ControllerSpec(
        modal_key='fi100_pv',
        engine_tag='TV-100.F',
        svg_id='fi-100',
        unit='lb/min',
        decimals=3,
        role='pv',
        writable=False,
        range=(0.0, 100.0),
        title='Steam Flow',
    ),
    ControllerSpec(
        modal_key='fi101_pv',
        engine_tag='STHR.F',
        svg_id='fi-101',
        unit='ft³/min',
        decimals=3,
        role='pv',
        writable=False,
        range=(0.0, 200.0),
        title='Feed Flow',
    ),
    # FI-102 is mirrored from FI-101 (product outflow == feed inflow
    # at steady state). The SignalHub copies `fi101_pv` → `fi102_pv`
    # via the ``derived_from`` field at the end of each tick.
    ControllerSpec(
        modal_key='fi102_pv',
        engine_tag=None,
        svg_id='fi-102',
        unit='ft³/min',
        decimals=3,
        role='pv',
        writable=False,
        range=(0.0, 200.0),
        derived_from='fi101_pv',
        title='Product Flow',
    ),
    ControllerSpec(
        modal_key='ti100_pv',
        engine_tag='STHR.Ti',
        svg_id='ti-100',
        unit='°F',
        decimals=1,
        role='pv',
        writable=False,
        range=(50.0, 250.0),
        title='Feed Temperature',
    ),
    ControllerSpec(
        modal_key='li100_pv',
        # plant has no level state — kept at SVG seed
        engine_tag=None,
        svg_id='li-100',
        unit='ft³',
        decimals=1,
        role='pv',
        writable=False,
        range=(0.0, 200.0),
        title='Tank Level',
    ),
    ControllerSpec(
        modal_key='vp100_pv',
        engine_tag='TV-100.vp',
        svg_id='vp-100',
        unit='%',
        decimals=1,
        role='pv',
        writable=False,
        range=(0.0, 100.0),
        title='Valve Position',
    ),
    # ── Indicator setpoints (so the legacy modal SP slots still
    #    have a writable target for FI-101 / TI-100) ──────────────
    ControllerSpec(
        modal_key='feed_flow',
        engine_tag='STHR.F',
        svg_id=None,
        unit='ft³/min',
        decimals=3,
        role='sp',
        writable=True,
        range=(0.0, 200.0),
    ),
    ControllerSpec(
        modal_key='feed_temp',
        engine_tag='STHR.Ti',
        svg_id=None,
        unit='°F',
        decimals=1,
        role='sp',
        writable=True,
        range=(50.0, 250.0),
    ),
    ControllerSpec(
        modal_key='steam_flow',
        engine_tag='STHR.W',
        svg_id=None,
        unit='lb/min',
        decimals=3,
        role='sp',
        writable=True,
        range=(0.0, 100.0),
    ),
]


STHR_REGISTRY: ControllerRegistry = ControllerRegistry(_SPECS)


__all__ = ['STHR_REGISTRY']
