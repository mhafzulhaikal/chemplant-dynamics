# app/pid/__init__.py

"""Per-case wiring for the hub-based control panel.

Each case ships:

- ``registry.py`` — declares a :class:`ControllerRegistry`
  (single source of truth for engine_tag ↔ modal_key ↔ svg_id ↔
  unit ↔ decimals).
- ``hub_factory.py`` — builds the per-browser bridge and the
  :class:`SignalHub` instance.
- ``view.py`` — renders the P&ID SVG; the SVG, faceplate, modal,
  data-logger and perf-monitor layers in :mod:`app.hub` drive the
  rest.
"""

__all__: list[str] = []
