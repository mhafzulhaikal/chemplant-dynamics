# models/actuator.py

import control as ct
import numpy as np


class ActuatorSystem:
    """Actuator control valve system model.

    Models a process control valve with configurable characteristics
    and response dynamics. Supports different valve types (linear,
    equal percentage, quick opening) and valve actions (fail-closed
    FC or fail-open FO).

    Parameters
    ----------
    name : str
        Descriptive name for the actuator (e.g., 'FCV_100')
    tauV : float
        Valve time constant [s]. Controls response speed. Must be >= 0.
    f_max : float
        Maximum flow rate [volumetric units/s]. Positive scalar.
    vp_min : float, optional
        Minimum valve position [%]. Default: 0.0
    vp_max : float, optional
        Maximum valve position [%]. Default: 100.0
    valve_type : str, optional
        Valve characteristic curve type. One of ['linear',
        'equal_percentage', 'quick_opening'].
        Default: 'linear'
    valve_action : str, optional
        Valve failure mode. One of ['FC' (fail-closed), 'FO' (fail-open)].
        Default: 'FC'
    """

    VALVE_TYPES = ['linear', 'equal_percentage', 'quick_opening']
    VALVE_ACTION = ['FC', 'FO']

    def __init__(
        self,
        name,
        tauV,
        f_max,
        vp_min=0.0,
        vp_max=100.0,
        valve_type='linear',
        valve_action='FC',
        dt=0.1,
    ):
        # Validate inputs
        if valve_type not in self.VALVE_TYPES:
            raise ValueError(
                f'Invalid valve type: {valve_type}. Must be one of {self.VALVE_TYPES}.'
            )

        if valve_action not in self.VALVE_ACTION:
            raise ValueError(
                f'Invalid valve action: {valve_action}. Must be one of {self.VALVE_ACTION}.'
            )

        if tauV < 0:
            raise ValueError(f'tauV must be non-negative, got {tauV}')

        if f_max <= 0:
            raise ValueError(f'f_max must be positive, got {f_max}')

        if vp_min >= vp_max:
            raise ValueError(f'vp_min ({vp_min}) must be less than vp_max ({vp_max})')

        self.params = {
            'name': name,
            'tauV': float(tauV),
            'f_max': float(f_max),
            'vp_min': float(vp_min),
            'vp_max': float(vp_max),
            'valve_type': valve_type,
            'valve_action': valve_action,
            'dt': float(dt),
        }

        self.system = ct.NonlinearIOSystem(
            updfcn=self.update,
            outfcn=self.output,
            name=self.params['name'],
            states=['vp'],
            outputs=['F'],
            inputs=['M'],
            dt=self.params['dt'],
        )

    @staticmethod
    def valve_characteristic(vp, valve_type):
        """Calculate valve flow characteristic normalized to 0-100%.

        Parameters
        ----------
        vp : float
            Valve position [%]
        valve_type : str
            Type of valve characteristic curve

        Returns
        -------
        float
            Normalized flow output [%]
        """
        vp = float(vp)

        if valve_type == 'linear':
            return vp
        elif valve_type == 'equal_percentage':
            return 100.0 * (50.0 ** (0.01 * vp - 1.0))
        elif valve_type == 'quick_opening':
            return 100.0 * np.sqrt(0.01 * vp)
        else:
            raise ValueError(f'Invalid valve type: {valve_type}')

    def update(self, t, x, u, params):
        vp = float(x[0])
        M = float(u[0])

        tauV = self.params['tauV']
        valve_action = self.params['valve_action']
        dt = self.params['dt']

        if valve_action == 'FC':
            u_eff = M
        elif valve_action == 'FO':
            u_eff = 100.0 - M
        else:
            raise ValueError(f'Invalid valve action: {valve_action}')

        if tauV <= 0:
            vp_next = u_eff
        else:
            a = np.exp(-dt / tauV)
            b = 1.0 - a
            vp_next = a * vp + b * u_eff

        vp_next = np.clip(vp_next, self.params['vp_min'], self.params['vp_max'])

        return [vp_next]

    def output(self, t, x, u, params):
        """Calculate actual flow rate from valve position.

        Parameters
        ----------
        t : float
            Current simulation time
        x : array_like
            State vector [vp] - valve position in %
        u : array_like
            Input vector [M] - controller output (unused)
        params : dict
            System parameters (unused, using self.params instead)

        Returns
        -------
        list
            Output vector [F] - actual flow rate
        """
        vp = float(x[0]) if x is not None and len(x) > 0 else 0.0
        f_max = self.params['f_max']
        vp_min = self.params['vp_min']
        vp_max = self.params['vp_max']
        valve_type = self.params['valve_type']

        # Clamp valve position to operating range
        vp_clamped = np.clip(vp, vp_min, vp_max)

        # Calculate normalized flow from valve characteristic
        flow_normalized = self.valve_characteristic(vp_clamped, valve_type)

        # Scale to actual flow rate
        F = (flow_normalized / 100.0) * f_max

        return [F]

    def __repr__(self):
        return repr(self.system)
