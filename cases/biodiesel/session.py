from __future__ import annotations

from cases.biodiesel import config as cfg
from cases.common.base_session import BaseSimulationSession
from engine.tag import Tag
from systems.builders.biodiesel_builder import (
    build_biodiesel_closed_loop_system,
)


class BiodieselSimulationSession(BaseSimulationSession):
    """Runtime session for Biodiesel reactor case."""

    PLANT_ID = 'BIODIESEL'

    def __init__(self, appdb, session_id: str = 'biodiesel-session', Ts: float = 0.5):
        self.appdb = appdb
        self.session_id = session_id
        self.time_unit = cfg.normalize_time_unit(cfg.SIMULATION_PARAMS.get('time_unit', 'seconds'))
        # _Ts_native: sample time in the model's own unit (seconds).
        # Used for system construction so that solve_ivp / PID / actuator
        # all integrate with the correct step size.
        _Ts_native = float(cfg.SIMULATION_PARAMS.get('Ts', Ts))
        # self.Ts: always in minutes — used by the bridge for clock
        # advancement.
        self.Ts = float(cfg.to_minutes(_Ts_native, self.time_unit))
        self.t = 0.0
        self._ts_buffer: list[dict] = []
        self._ts_buffer_size: int = int(cfg.SIMULATION_PARAMS.get('timeseries_buffer', 100))

        self._build_runner_and_tags(self.resolve_mode(), _Ts_native)

    def refresh_runtime_parameters(self) -> None:
        self.time_unit = cfg.normalize_time_unit(
            cfg.SIMULATION_PARAMS.get('time_unit', self.time_unit)
        )
        _Ts_native = float(cfg.SIMULATION_PARAMS.get('Ts', self.Ts))
        self.Ts = float(cfg.to_minutes(_Ts_native, self.time_unit))
        self._ts_buffer_size = int(
            cfg.SIMULATION_PARAMS.get('timeseries_buffer', self._ts_buffer_size)
        )

    def resolve_mode(self) -> str:
        return str(cfg.CONTROLLER_MODE.get('Mode', 'Automatic'))

    def _classify_output_signal(self, name: str) -> str:
        if name.startswith('biodiesel_reactor.'):
            return 'PV'
        if name.endswith('.R'):
            return 'SP'
        if name.endswith('.M') or name.endswith('.F'):
            return 'MV'
        return 'PV'

    def resolve_runtime(self, mode: str, ts: float):
        mode_lc = mode.strip().lower()

        if mode_lc in {'automatic', 'manual', 'off'}:
            loop_modes = cfg.resolve_loop_modes(mode_lc)
            system, inplist, outlist = build_biodiesel_closed_loop_system(ts, loop_modes=loop_modes)
            _initial_states = cfg.default_initial_states()
            _state_labels_x0 = getattr(system, 'state_labels', None) or []
            x0 = [
                float(_initial_states.get(self._state_tag_name(lbl), 0.0))
                for lbl in _state_labels_x0
            ]
            output_tags = self._default_output_tags(outlist)
        else:
            system = None
            inplist = []
            outlist = []
            x0 = []
            output_tags = {}

        input_tags: dict[str, Tag] = {
            name: Tag(name, 'SP' if name.endswith('.SP') else 'IN') for name in inplist
        }

        state_tags: dict[str, Tag] = {}
        if system is not None:
            state_labels = getattr(system, 'state_labels', None) or []
            for name in state_labels:
                state_tags[name] = Tag(self._state_tag_name(name), 'ST')

        return (system, inplist, outlist, x0, input_tags, state_tags, output_tags)

    def _state_tag_name(self, state_label: str) -> str:
        # The biodiesel plant system is named 'biodiesel_reactor', which itself
        # contains an underscore.  Replacing only the first '_' would yield
        # 'biodiesel.reactor_h' instead of the correct 'biodiesel_reactor.h'.
        _PLANT_PREFIX = 'biodiesel_reactor_'
        if state_label.startswith(_PLANT_PREFIX):
            return 'biodiesel_reactor.' + state_label[len(_PLANT_PREFIX) :]
        return state_label.replace('_', '.', 1)

    def prepare_inputs(self, external_inputs: dict | None = None) -> dict:
        return cfg.prepare_external_inputs(self.mode_key, external_inputs)


def create_session(appdb):
    def factory() -> BiodieselSimulationSession:
        return BiodieselSimulationSession(appdb=appdb)

    return factory
