# models/sensor.py

import control as ct
import numpy as np


class SensorTransmitterSystem:
    """Process sensor with transmitter and first-order lag dynamics.

    Models a measurement sensor with optional dynamic response
    (first-order lag).
    Converts raw process variable to normalized 0-100% output signal.
    Simulates realistic sensor response dynamics and measurement range.

    Parameters
    ----------
    name : str
        Descriptive name for the sensor transmitter (e.g., 'LT_100', 'TT_100')
    hi : float
        Upper measurement range limit (100% output value)
    low : float
        Lower measurement range limit (0% output value)
    tauT : float
        Sensor time constant [s]. Controls response speed.
        - If tauT > 0: first-order lag dynamics (realistic sensor response)
        - If tauT = 0: instantaneous sensor (zero lag)
        - If tauT < 0: invalid (raises ValueError)

    Notes
    -----
    The transmitter scales the process variable (PV) to 0-100% output range:
        C = (PV - low) / (hi - low) * 100

    The time constant tauT models sensor/transmitter delay:
        dPVm/dt = (PV - PVm) / tauT

    where PVm is the measured (filtered) PV and C is the 0-100% output.
    """

    def __init__(self, name, hi, low, tauT, dt=0.1):
        # Validate parameters
        if hi <= low:
            raise ValueError(f'hi ({hi}) must be greater than low ({low})')

        if tauT < 0:
            raise ValueError(f'tauT must be non-negative, got {tauT}')

        self.params = {
            'name': str(name),
            'hi': float(hi),
            'low': float(low),
            'tauT': float(tauT),
            'Ts': float(dt),
        }

        # Create system with or without dynamics based on tauT
        if self.params['tauT'] > 0:
            # First-order lag: dynamic response
            self.system = ct.NonlinearIOSystem(
                updfcn=self.update,
                outfcn=self.output,
                name=self.params['name'],
                states=['PVm'],
                outputs=['C'],
                inputs=['PV'],
                dt=self.params['Ts'],
            )
        else:
            # No dynamics: instantaneous response
            self.system = ct.NonlinearIOSystem(
                updfcn=None,
                outfcn=self.output,
                name=self.params['name'],
                outputs=['C'],
                inputs=['PV'],
                dt=self.params['Ts'],
            )

    def update(self, t, x, u, params):
        """
        DISCRETE-TIME sensor dynamics:
        returns next state PVm[k+1]
        """

        PVm = float(x[0])
        PV = float(u[0])
        tauT = self.params['tauT']
        Ts = self.params['Ts']

        # If tauT > 0 → dynamic sensor
        if tauT > 0:
            # ✅ exact discretization of first-order lag
            a = np.exp(-Ts / tauT)
            PVm_next = a * PVm + (1.0 - a) * PV
        else:
            # instantaneous sensor (should not reach here if using None system)
            PVm_next = PV

        return [PVm_next]

    def output(self, t, x, u, params):
        """Sensor output: scale measured value to 0-100% range.

        Parameters
        ----------
        t : float
            Current simulation time [s]
        x : array_like
            State vector [PVm] - measured process variable
            Can be None if no dynamics (tauT = 0)
        u : array_like
            Input vector [PV] - actual process variable
        params : dict
            System parameters (unused, using self.params)

        Returns
        -------
        list
            Output vector [C] - normalized signal 0-100%
        """
        # Select measurement source: use state if available (with dynamics),
        # else input (no dynamics)
        PVm = float(x[0]) if x is not None and len(x) > 0 else float(u[0])

        hi = self.params['hi']
        low = self.params['low']

        # Linear scaling to 0-100% range
        C = (PVm - low) / (hi - low) * 100.0 if hi != low else 0.0

        return [C]

    def __repr__(self):
        return repr(self.system)
