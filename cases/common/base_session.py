# cases/common/base_session.py
"""Base simulation session shared by all cases."""

from __future__ import annotations

from typing import Any

from engine.appdb import add_tag, append_timeseries_records
from engine.step_io_runner import StepInputOutputRunner
from engine.tag import Tag


class BaseSimulationSession:
    """
    Shared runtime session logic for all simulation cases.

    Subclass responsibilities:
      - Set self.appdb, self.session_id, self.time_unit, self.Ts (minutes),
        self.t, self._ts_buffer, self._ts_buffer_size  before calling
        _build_runner_and_tags().
      - Override all abstract methods below.

    Class attribute:
      PLANT_ID: str — identifier written to timeseries records (e.g. 'STHR').
    """

    PLANT_ID: str = 'UNKNOWN'

    # Instance attributes — subclasses must set these before calling
    # _build_runner_and_tags().
    appdb: Any
    session_id: str
    Ts: float
    t: float
    _ts_buffer: list[dict[str, Any]]
    _ts_buffer_size: int

    # ------------------------------------------------------------------
    # Setup helper — call at end of subclass __init__
    # ------------------------------------------------------------------

    def _build_runner_and_tags(self, mode: str, Ts_native: float) -> None:
        """Build the runner, tag maps, and expose them as attributes.

        Parameters
        ----------
        mode:
            Raw mode string (e.g. 'Automatic').
        Ts_native:
            Sample time in the model's own unit (e.g. seconds for biodiesel,
            minutes for STHR).  Used to construct the closed-loop system so
            solve_ivp / PID / actuator all see the correct step size.
        """
        self.mode = mode
        self.mode_key = mode.strip().lower()

        (
            self.system,
            self.inplist,
            self.outlist,
            self.X0,
            self.input_tags,
            self.state_tags,
            self.output_tags,
        ) = self.resolve_runtime(mode, Ts_native)

        self.runner = (
            StepInputOutputRunner(
                sys=self.system,
                dt=self.Ts,
                x0=self.X0,
                input_labels=self.inplist,
                output_labels=self.outlist,
                output_timing='pre',
            )
            if self.system is not None
            else None
        )

        self.all_tags: dict[str, Tag] = {
            **self.input_tags,
            **self.state_tags,
            **self.output_tags,
        }

        self.last_inputs: dict[str, float] = {}
        self.last_states: dict[str, float] = {}
        self.last_outputs: dict[str, float] = {}

        for tag in self.all_tags.values():
            add_tag(self.appdb, tag)

    # ------------------------------------------------------------------
    # Abstract methods — subclasses must override
    # ------------------------------------------------------------------

    def resolve_mode(self) -> str:
        raise NotImplementedError

    def refresh_runtime_parameters(self) -> None:
        raise NotImplementedError

    def _classify_output_signal(self, name: str) -> str:
        raise NotImplementedError

    def resolve_runtime(
        self, mode: str, ts: float
    ) -> tuple[
        Any | None,
        list[str],
        list[str],
        list[float],
        dict[str, Tag],
        dict[str, Tag],
        dict[str, Tag],
    ]:
        raise NotImplementedError

    def _state_tag_name(self, state_label: str) -> str:
        raise NotImplementedError

    def prepare_inputs(self, external_inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _default_output_tags(self, outlist: list[str]) -> dict[str, Tag]:
        return {name: Tag(name, self._classify_output_signal(name)) for name in outlist}

    # ------------------------------------------------------------------
    # Runtime — step & flush (identical across all cases)
    # ------------------------------------------------------------------

    def step(self, external_inputs: dict | None = None) -> dict:
        """Run one simulation step and buffer data to appdb."""
        if self.runner is None:
            return {}

        u_ext = self.prepare_inputs(external_inputs)
        x_before = self.runner.state()
        y = self.runner.step(u_ext)

        state_labels = getattr(self.runner.sys, 'state_labels', None) or []

        self.last_inputs = dict(u_ext)
        self.last_states = {}
        self.last_outputs = {}

        records: list[dict] = []

        for key, value in u_ext.items():
            tag = self.input_tags.get(key)
            if tag is not None:
                records.append(
                    {'plant_id': self.PLANT_ID, 'tag': tag.name, 't': self.t, 'value': float(value)}
                )

        for idx, key in enumerate(state_labels):
            tag = self.state_tags.get(key)
            if tag is not None and idx < len(x_before):
                self.last_states[tag.name] = float(x_before[idx])
                records.append(
                    {
                        'plant_id': self.PLANT_ID,
                        'tag': tag.name,
                        't': self.t,
                        'value': float(x_before[idx]),
                    }
                )

        for key, value in y.items():
            tag = self.output_tags.get(key)
            if tag is not None:
                self.last_outputs[tag.name] = float(value)
                records.append(
                    {'plant_id': self.PLANT_ID, 'tag': tag.name, 't': self.t, 'value': float(value)}
                )

        if records:
            self._ts_buffer.extend(records)
            if len(self._ts_buffer) >= self._ts_buffer_size:
                try:
                    append_timeseries_records(self.appdb, self._ts_buffer)
                finally:
                    self._ts_buffer.clear()

        self.t += self.Ts
        return y

    def flush_timeseries_buffer(self) -> None:
        """Flush any buffered timeseries records to the global appdb."""
        if not self._ts_buffer:
            return
        try:
            append_timeseries_records(self.appdb, self._ts_buffer)
        finally:
            self._ts_buffer.clear()
