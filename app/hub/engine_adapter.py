# app/hub/engine_adapter.py

"""Pure Python engine bridge adapter.

This module provides a strict seam between the high-frequency UI store
and the multiprocess bridge. It handles all record draining and parsing
without any UI dependencies.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


def mode_name_to_code(name: str) -> int:
    """Modals encode controller mode as 0=Off, 1=Manual, 2=Auto."""
    return {'off': 0, 'manual': 1, 'automatic': 2, 'auto': 2}.get(
        str(name or '').strip().lower(),
        2,
    )


def mode_code_to_name(code: int) -> str:
    return {0: 'Off', 1: 'Manual', 2: 'Automatic'}.get(int(code), 'Automatic')


@dataclass(slots=True, frozen=True)
class TickMeta:
    """Per-tick metadata that accompanies every ``on_tick`` dispatch."""

    sim_time: float
    step_index: int
    status: str
    mode: str
    reset_counter: int


class EngineBridgeAdapter:
    """Pure adapter for draining engine IPC queues into UI deltas.

    Maintains internal clock tracking so even when no data arrives, it
    can report the latest status/time.
    """

    def __init__(
        self,
        bridge: Any,
        output_to_pv: Mapping[str, list[str]],
        input_map: Mapping[str, str],
        status_keys: tuple[str, ...],
    ) -> None:
        self._bridge = bridge
        self._output_to_pv = output_to_pv
        self._input_field_to_override = input_map
        self._status_keys = status_keys

        self._sim_time: float = 0.0
        self._step_index: int = -1
        self._status: str = str(getattr(bridge.state, 'status', 'idle') or 'idle')
        self._mode: str = str(
            getattr(bridge.state, 'controller_mode', '') or 'Automatic',
        )
        self._reset_counter: int = 0

    def reset(self) -> None:
        """Reset internal time and step tracking on simulation reset."""
        self._sim_time = 0.0
        self._step_index = -1
        self._reset_counter += 1

    def set_input_value(self, engine_tag: str, value: float) -> None:
        """Forward a raw input value to the bridge."""
        self._bridge.set_input_value(engine_tag, float(value))

    def apply_runtime_configuration(self, restart_if_needed: bool = False) -> None:
        """Trigger a runtime configuration apply."""
        self._bridge.apply_runtime_configuration(restart_if_needed=restart_if_needed)

    def set_controller_mode(self, mode_name: str) -> None:
        """Update global bridge controller mode and apply."""
        self._bridge.state.controller_mode = mode_name
        self.apply_runtime_configuration(restart_if_needed=True)

    def drain_and_parse(self, max_records: int) -> tuple[dict[str, float], TickMeta, list[dict]]:
        """Drain bridge records and fold them into a unified delta dict.

        Returns (delta_dict, tick_meta).
        """
        try:
            records = self._bridge.drain_records(max_records)
        except Exception:
            logger.exception('EngineBridgeAdapter: drain_records failed')
            records = []

        delta: dict[str, float] = {}
        raw_steps: list[dict] = []
        last_step_record = None
        has_steps = False

        for r in records:
            kind = getattr(r, 'kind', None)
            if kind == 'step':
                has_steps = True
                last_step_record = r
                raw_steps.append(
                    {
                        'step_index': r.step_index,
                        'time_min': r.time_min,
                        'inputs': r.inputs,
                        'states': r.states,
                        'outputs': r.outputs,
                    }
                )
            elif kind == 'status':
                self._fold_status(r, delta)

        if last_step_record is not None:
            self._fold_step(last_step_record, delta)

        # Update tracking state from bridge state safely.
        # Step records (folded above) already updated self._step_index and
        # self._sim_time via _fold_step. Bridge.state is used as a fallback
        # only when no step records arrived this tick.
        try:
            bridge_state = self._bridge.state
            self._status = str(
                getattr(bridge_state, 'status', self._status) or self._status,
            )
            self._mode = str(
                getattr(bridge_state, 'controller_mode', self._mode) or self._mode,
            )
            if not has_steps:
                # No step records this tick — fall back to bridge state clock monotonically.
                fallback_t = getattr(bridge_state, 'global_sim_time', None)
                if fallback_t is not None:
                    try:
                        f_val = float(fallback_t)
                        if f_val >= self._sim_time:
                            self._sim_time = f_val
                    except (TypeError, ValueError):
                        pass
                bridge_last = getattr(bridge_state, 'last_step', None)
                if bridge_last is not None and bridge_last >= 0:
                    try:
                        s_val = int(bridge_last)
                        if s_val >= self._step_index:
                            self._step_index = s_val
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass

        meta = TickMeta(
            sim_time=self._sim_time,
            step_index=self._step_index,
            status=self._status,
            mode=self._mode,
            reset_counter=self._reset_counter,
        )

        return delta, meta, raw_steps

    def drain_one(self) -> tuple[dict[str, float], TickMeta, dict | None]:
        """Drain exactly ONE step record from the engine queue.

        This is the step-aligned drain used by the high-frequency UI path.
        Each call either:
        - Returns (delta, meta, step_dict) when a physics step is consumed.
        - Returns (delta, meta, None) when only status records are available
          or the queue is empty (delta may still contain status updates).

        By consuming one step at a time, the UI snapshot always represents a
        single coherent physics state: t=0.01 → T=160F, t=0.02 → T=162F, etc.
        """
        try:
            records = self._bridge.drain_records(1)
        except Exception:
            logger.exception('EngineBridgeAdapter: drain_records(1) failed')
            records = []

        delta: dict[str, float] = {}
        raw_step: dict | None = None

        # If we only got status records or nothing, try to drain a few more
        # status records to stay current (they are cheap).
        if not records or all(getattr(r, 'kind', None) != 'step' for r in records):
            try:
                extra = self._bridge.drain_records(8)
                records = list(records) + list(extra)
            except Exception:
                pass

        step_record = None
        for r in records:
            kind = getattr(r, 'kind', None)
            if kind == 'step' and step_record is None:
                step_record = r
            elif kind == 'status':
                self._fold_status(r, delta)

        if step_record is not None:
            self._fold_step(step_record, delta)
            raw_step = {
                'step_index': step_record.step_index,
                'time_min': step_record.time_min,
                'inputs': step_record.inputs,
                'states': step_record.states,
                'outputs': step_record.outputs,
            }

        # Update tracking state from bridge state.
        try:
            bridge_state = self._bridge.state
            self._status = str(
                getattr(bridge_state, 'status', self._status) or self._status,
            )
            self._mode = str(
                getattr(bridge_state, 'controller_mode', self._mode) or self._mode,
            )
            if step_record is None:
                fallback_t = getattr(bridge_state, 'global_sim_time', None)
                if fallback_t is not None:
                    try:
                        f_val = float(fallback_t)
                        if f_val >= self._sim_time:
                            self._sim_time = f_val
                    except (TypeError, ValueError):
                        pass
                bridge_last = getattr(bridge_state, 'last_step', None)
                if bridge_last is not None and bridge_last >= 0:
                    try:
                        s_val = int(bridge_last)
                        if s_val >= self._step_index:
                            self._step_index = s_val
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass

        meta = TickMeta(
            sim_time=self._sim_time,
            step_index=self._step_index,
            status=self._status,
            mode=self._mode,
            reset_counter=self._reset_counter,
        )

        return delta, meta, raw_step

    def _fold_step(
        self,
        record: Any,
        delta: dict[str, float],
    ) -> None:
        inputs = getattr(record, 'inputs', None) or {}
        states = getattr(record, 'states', None) or {}
        outputs = getattr(record, 'outputs', None) or {}

        # outputs > states > inputs
        for engine_tag, modal_keys in self._output_to_pv.items():
            source: float | None = None
            if engine_tag in outputs:
                source = self._safe_float(outputs[engine_tag])
            elif engine_tag in states:
                source = self._safe_float(states[engine_tag])
            elif engine_tag in inputs:
                source = self._safe_float(inputs[engine_tag])
            if source is not None:
                for modal_key in modal_keys:
                    delta[modal_key] = source

        # Input echo — only fills modal keys not already in delta.
        for engine_tag, modal_key in self._input_field_to_override.items():
            if modal_key in delta:
                continue
            if engine_tag in inputs:
                v = self._safe_float(inputs[engine_tag])
                if v is not None:
                    delta[modal_key] = v

        # Status keys
        mode_text = getattr(record, 'mode', None) or ''
        if mode_text:
            code = float(mode_name_to_code(mode_text))
            for sk in self._status_keys:
                delta[sk] = code

        # Step / time bookkeeping (strictly monotonic within this lifecycle)
        if getattr(record, 'time_min', None) is not None:
            try:
                new_t = float(record.time_min)
                if new_t >= self._sim_time:
                    self._sim_time = new_t
            except (TypeError, ValueError):
                pass
        if getattr(record, 'step_index', None) is not None:
            try:
                new_step = int(record.step_index)
                if new_step >= self._step_index:
                    self._step_index = new_step
            except (TypeError, ValueError):
                pass

    def _fold_status(
        self,
        record: Any,
        delta: dict[str, float],
    ) -> None:
        mode_text = getattr(record, 'mode', None) or ''
        if mode_text:
            code = float(mode_name_to_code(mode_text))
            for sk in self._status_keys:
                delta[sk] = code

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
