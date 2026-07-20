# cases/sthr/session.py

from cases.common import merge_input_dicts
from cases.common.base_session import BaseSimulationSession
from cases.sthr import config as cfg
from engine.tag import Tag
from systems.builders.sthr_builder import build_sthr_closed_loop_system


class STHRSimulationSession(BaseSimulationSession):
    """
    Runtime session that connects:
      model runner -> appdb historian
    """

    PLANT_ID = 'STHR'

    def __init__(self, appdb, session_id='sthr-session', Ts=0.01):
        self.appdb = appdb
        self.session_id = session_id
        self.time_unit = cfg.normalize_time_unit(cfg.SIMULATION_PARAMS.get('time_unit', 'minutes'))
        self.Ts = float(cfg.to_minutes(cfg.SIMULATION_PARAMS.get('Ts', Ts), self.time_unit))
        self.t = 0.0
        self._ts_buffer: list[dict] = []
        self._ts_buffer_size: int = int(cfg.SIMULATION_PARAMS.get('timeseries_buffer', 100))

        self._build_runner_and_tags(self.resolve_mode(), self.Ts)

    def refresh_runtime_parameters(self) -> None:
        self.time_unit = cfg.normalize_time_unit(
            cfg.SIMULATION_PARAMS.get('time_unit', self.time_unit)
        )
        self.Ts = float(cfg.to_minutes(cfg.SIMULATION_PARAMS.get('Ts', self.Ts), self.time_unit))
        self._ts_buffer_size = int(
            cfg.SIMULATION_PARAMS.get('timeseries_buffer', self._ts_buffer_size)
        )

    def resolve_mode(self) -> str:
        return str(cfg.CONTROLLER_MODE.get('Mode', 'Off'))

    def _classify_output_signal(self, name: str) -> str:
        if name.startswith('STHR.'):
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
            system, inplist, outlist = build_sthr_closed_loop_system(ts, loop_modes=loop_modes)
            _initial_states: dict[str, float] = {}
            _initial_states.update(cfg.PLANT_OUTPUT)
            _initial_states.update(cfg.SENSOR_TRANSMITTER_STATE)
            _initial_states.update(cfg.CONTROLLER_STATE)
            _initial_states.update(cfg.ACTUATOR_STATE)
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
        return state_label.replace('_', '.', 1)

    def prepare_inputs(self, external_inputs: dict | None = None) -> dict:
        inputs = cfg.default_inputs_for_mode(self.mode_key)
        if not inputs:
            return {}
        return merge_input_dicts(inputs, external_inputs)
