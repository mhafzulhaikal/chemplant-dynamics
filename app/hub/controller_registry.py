# app/hub/controller_registry.py

"""Single source of truth for per-controller metadata.

In the legacy stack the same controller metadata was declared in
five different places:

- ``output_to_pv``           in ``app/pid/<case>/bridge_store.py``
- ``input_field_to_override`` in ``app/pid/<case>/bridge_store.py``
- ``controller_to_pv_key``    in ``app/pid/<case>/live_flusher.py``
- ``controller_to_unit``      in ``app/pid/<case>/live_flusher.py``
- ``controller_to_decimals``  in ``app/pid/<case>/live_flusher.py``
- ``DISPLAY_MAP``             in ``app/config.py``
- ``CONTROLLER_DRAWER_CONFIG`` in ``app/config.py``
- ``FaceplateSpec.decimals_map`` in ``app/components/faceplate.py``

Every map redeclared the same controller ids, with subtly different
defaults — a known drift hazard. The hub stack collapses all of
those into a single per-case :class:`ControllerRegistry`. Children
(SVG, faceplate, modal, data logger, perf chart) look up everything
from the same registry, so adding a new controller or changing a
unit only touches one file.

The registry is intentionally case-agnostic — STHR ships
``STHR_REGISTRY`` in ``app/pid/sthr/registry.py``; biodiesel
ships its own. The hub wires whichever registry the page passes in.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Literal

Role = Literal['pv', 'sp', 'op', 'tuning', 'status']


@dataclass(frozen=True)
class ControllerSpec:
    """Static metadata for one logical signal in one case.

    Every distinct ``modal_key`` (the key the modal / store / hub
    snapshot is indexed by) gets exactly one spec. A controller
    like TIC-100 therefore contributes multiple specs (one per
    role: ``pv``, ``sp``, ``op``, ``kc`` …).

    Attributes
    ----------
    modal_key:
        The hub snapshot key. Must be unique within a registry.
    engine_tag:
        The bridge / engine tag that publishes this signal. When
        the role is ``pv`` this is the tag the spec is READ from
        (``output_to_pv``-style). When the role is ``sp`` / ``op``
        / ``tuning`` / ``status`` this is the tag the spec is
        WRITTEN to (``input_field_to_override``-style). May be
        ``None`` for UI-only modal keys.
    svg_id:
        The SVG controller card id (e.g. ``'tic-100'``). When set,
        the :class:`SvgChild` updates the ``<text id="{svg_id}-value">``
        element with the formatted snapshot value. ``None`` skips
        the SVG render entirely.
    unit, decimals:
        Display formatting (rounded to ``decimals`` decimal places,
        then suffixed with ``unit``). Used by every child that
        renders a numeric value.
    role:
        ``'pv'`` (process variable, read-only), ``'sp'`` (setpoint,
        operator-writable), ``'op'`` (controller output, sometimes
        writable in manual mode), ``'tuning'`` (Kc / τI / τD,
        writable), ``'status'`` (controller mode 0/1/2, routes
        through ``apply_runtime_configuration``).
    writable:
        ``True`` when ``SignalHub.request_write(modal_key, value)``
        is allowed. PVs are typically ``False``; SP/Kc/τI/τD ``True``.
    range:
        Optional ``(min, max)`` for display bargraph fills /
        validation. ``None`` means "use the unit-based default".
    derived_from:
        Optional modal_key this spec mirrors. The hub copies the
        source key's value into this spec at the end of
        ``_apply_records_to_snapshot``. Used by STHR's FI-102
        (mirror of FI-101) where the engine emits only one feed-flow
        tag for both indicators.
    title:
        Human label used by the faceplate header (e.g.
        ``"Temperature Controller"``). Falls back to ``modal_key``.
    """

    modal_key: str
    engine_tag: str | None
    svg_id: str | None = None
    unit: str = ''
    decimals: int = 1
    role: Role = 'pv'
    writable: bool = False
    range: tuple[float, float] | None = None
    derived_from: str | None = None
    title: str = ''
    display_scale: float = 1.0


class ControllerRegistry:
    """Indexed collection of :class:`ControllerSpec` for one case.

    Provides O(1) lookup by every dimension the children care about
    (``modal_key``, ``engine_tag``, ``svg_id``) and pre-computed derived
    sets (``writable_keys``, ``svg_emitters``, the output/input map
    projections the hub needs each tick).

    The registry is **immutable after construction** — pass the full
    spec list to ``__init__``. Adding a spec later means building a new
    registry. This keeps lookups lock-free and the snapshot schema
    stable across the page's lifetime.
    """

    __slots__ = (
        '_specs',
        '_by_modal_key',
        '_by_engine_tag',
        '_by_svg_id',
        '_writable_keys',
        '_status_keys',
        '_svg_emitters',
        '_output_to_pv',
        '_input_field_to_override',
        '_derived_pairs',
    )

    def __init__(self, specs: list[ControllerSpec]) -> None:
        # Defensive copy + uniqueness check on modal_key.
        seen: set[str] = set()
        deduped: list[ControllerSpec] = []
        for spec in specs:
            if spec.modal_key in seen:
                raise ValueError(
                    f'ControllerRegistry: duplicate modal_key {spec.modal_key!r}',
                )
            seen.add(spec.modal_key)
            deduped.append(spec)

        self._specs: tuple[ControllerSpec, ...] = tuple(deduped)
        self._by_modal_key: dict[str, ControllerSpec] = {
            spec.modal_key: spec for spec in self._specs
        }

        # engine_tag → spec (only for specs that have one). For roles
        # ``pv``/``sp``/``op``/``tuning`` an engine_tag is a 1:1 map
        # under normal cases; if two specs reference the same engine
        # tag the LAST one wins — by convention the writable spec
        # comes after the read-only one (see STHR ``op`` ↔ ``TV-100.M``
        # vs ``TC-100.M`` discussion in app/pid/sthr/bridge_store.py).
        self._by_engine_tag: dict[str, ControllerSpec] = {}
        for spec in self._specs:
            if spec.engine_tag:
                self._by_engine_tag[spec.engine_tag] = spec

        self._by_svg_id: dict[str, ControllerSpec] = {
            spec.svg_id: spec for spec in self._specs if spec.svg_id
        }

        self._writable_keys: tuple[str, ...] = tuple(
            spec.modal_key for spec in self._specs if spec.writable
        )
        self._status_keys: tuple[str, ...] = tuple(
            spec.modal_key for spec in self._specs if spec.role == 'status'
        )
        self._svg_emitters: tuple[ControllerSpec, ...] = tuple(
            spec for spec in self._specs if spec.svg_id
        )

        # Pre-computed projections the hub uses every tick. Stored
        # once so the per-tick loop is allocation-free.
        # output_to_pv: engine_tag → [modal_key, …] (for role='pv'/'op'
        # roles that are RECEIVED from the engine). One engine tag
        # may feed multiple modal keys (e.g. biodiesel_reactor.T_coolant
        # feeds both ti104_pv and tic_coolant_temp).
        self._output_to_pv: dict[str, list[str]] = {}
        for spec in self._specs:
            if spec.engine_tag and spec.role in ('pv', 'op'):
                self._output_to_pv.setdefault(
                    spec.engine_tag,
                    [],
                ).append(spec.modal_key)
        # input_field_to_override: engine_tag → modal_key (for
        # writable roles).
        self._input_field_to_override: dict[str, str] = {
            spec.engine_tag: spec.modal_key
            for spec in self._specs
            if spec.engine_tag and spec.writable
        }

        # (source_modal_key, target_modal_key) for derived mirrors.
        self._derived_pairs: tuple[tuple[str, str], ...] = tuple(
            (spec.derived_from, spec.modal_key) for spec in self._specs if spec.derived_from
        )

    # ---------------------------------------------------------------
    # Lookups
    # ---------------------------------------------------------------

    def by_modal_key(self, modal_key: str) -> ControllerSpec:
        return self._by_modal_key[modal_key]

    def get_by_modal_key(self, modal_key: str) -> ControllerSpec | None:
        return self._by_modal_key.get(modal_key)

    def by_engine_tag(self, engine_tag: str) -> ControllerSpec | None:
        return self._by_engine_tag.get(engine_tag)

    def by_svg_id(self, svg_id: str) -> ControllerSpec | None:
        return self._by_svg_id.get(svg_id)

    def writable_keys(self) -> tuple[str, ...]:
        return self._writable_keys

    def status_keys(self) -> tuple[str, ...]:
        return self._status_keys

    def svg_emitters(self) -> tuple[ControllerSpec, ...]:
        return self._svg_emitters

    def output_to_pv(self) -> Mapping[str, list[str]]:
        """Engine tag → list of modal keys.

        Read by ``SignalHub._apply_records``.
        """
        return self._output_to_pv

    def input_field_to_override(self) -> Mapping[str, str]:
        """Engine tag → modal key.

        Read by ``SignalHub._consume_step_record``.
        """
        return self._input_field_to_override

    def derived_pairs(self) -> tuple[tuple[str, str], ...]:
        """(source_modal_key, target_modal_key) mirror pairs."""
        return self._derived_pairs

    def __iter__(self) -> Iterator[ControllerSpec]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    # ---------------------------------------------------------------
    # Display formatting (used by every numeric child)
    # ---------------------------------------------------------------

    def _is_flow_spec(self, spec: ControllerSpec) -> bool:
        """Detect if ``spec`` represents a per-second flow rate.

        Flow specs are identified by their display unit containing
        ``/h`` (e.g. ``m³/h``), which signals that the raw engine
        value is in per-second and must be scaled to per-hour.
        """
        unit = spec.unit.lower()
        return '/h' in unit or 'hr' in unit or 'per hour' in unit

    def format(self, modal_key: str, value: float | None) -> str:
        """Render ``value`` per this spec's ``decimals`` + ``unit``.

        Accepts ``None`` (returns the em-dash placeholder) so callers
        can pass ``snapshot.get(key)`` directly without a guard. Mirrors
        the legacy ``BaseLiveFlusher._format_value`` so SVG text and
        faceplate values look identical between v1 and v2.

        Flow-rate specs (unit ``m³/h``, etc.) are automatically scaled
        from per-second engine values to per-hour display.
        """
        spec = self._by_modal_key.get(modal_key)
        if spec is None:
            return f'{value}'
        if value is None:
            return '—'
        try:
            f = float(value)
        except (TypeError, ValueError):
            return f'{value} {spec.unit}'.strip()
        if self._is_flow_spec(spec):
            f *= 3600.0
        rounded = round(f, spec.decimals)
        return f'{rounded} {spec.unit}'.strip()

    def get_spec_by_engine_tag(self, engine_tag: str) -> ControllerSpec | None:
        """Return the ControllerSpec for an engine tag, if any."""
        return self._by_engine_tag.get(engine_tag)

    def get_unit_for(self, field_name: str) -> str:
        """Fallback rule-based unit inference for tags (like data_logger
        used)."""
        scope, _, tag = field_name.partition(':')

        if scope == 'meta':
            if tag == 'step':
                return '#'
            if tag == 'time':
                return 'min'
            if tag == 'mode':
                return '—'
            return ''

        if not tag:
            return ''

        spec = self.get_spec_by_engine_tag(tag)
        if spec and spec.unit:
            return spec.unit

        # Fallbacks (e.g. unmapped engine tags)
        head, _, suffix = tag.rpartition('.')
        if suffix in {'C', 'M', 'R', 'vp', 'I_state', 'D_state'}:
            return '%'
        if suffix in {'Kc'}:
            return '—'
        if suffix in {'tauI', 'tauD'}:
            return 'min'
        if suffix in {'SP', 'PV', 'PVm'} and tag[0] in {
            'T': '°C',
            'L': 'm',
            'F': 'kg/h',
            'P': 'bar',
        }:
            return {'T': '°C', 'L': 'm', 'F': 'kg/h', 'P': 'bar'}[tag[0]]

        if tag in {
            'W': 'kg/h',
            'F': 'kg/h',
            'Ti': '°C',
            'T': '°C',
            'Ts': '°C',
            'L': 'm',
            'V': 'm³',
        }:
            return {
                'W': 'kg/h',
                'F': 'kg/h',
                'Ti': '°C',
                'T': '°C',
                'Ts': '°C',
                'L': 'm',
                'V': 'm³',
            }[tag]

        return ''

    def get_scale_for(self, field_name: str) -> float:
        """Fallback rule-based scaling factor inference for tags (like
        perf_monitor used)."""
        scope, _, tag = field_name.partition(':')
        if not tag:
            return 1.0

        spec = self.get_spec_by_engine_tag(tag)
        if spec:
            if spec.display_scale != 1.0:
                return spec.display_scale
            if self._is_flow_spec(spec):
                return 3600.0

        # Fallbacks for unmapped tags
        tag_upper = tag.upper()
        head, _, suffix = tag_upper.rpartition('.')
        if suffix in {
            'C',
            'M',
            'R',
            'VP',
            'I_STATE',
            'D_STATE',
            'KC',
            'TAUI',
            'TAUD',
        }:
            return 1.0

        if tag_upper.startswith('FSP') or tag_upper.startswith('F_') or 'F_' in tag_upper:
            return 3600.0

        return 1.0


__all__ = ['ControllerRegistry', 'ControllerSpec', 'Role']
