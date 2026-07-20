# models/setpoint.py

import control as ct


class SetPointSystem:
    """Setpoint normalizer: scales engineering setpoint values to
    0-100% signal.

    Converts raw setpoint values (in process units) to normalized
    0-100% control signal.
    This system has no dynamics - it provides instantaneous scaling.

    Parameters
    ----------
    name : str
        Descriptive name for the setpoint system (e.g., 'LSP_100', 'TSP_100')
    hi : float
        Upper setpoint range limit (100% output value)
        Engineering units (e.g., m³ for level, K for temperature)
    low : float
        Lower setpoint range limit (0% output value)
        Engineering units (e.g., m³ for level, K for temperature)

    Notes
    -----
    The setpoint system performs linear scaling:
        R = (SP - low) / (hi - low) * 100

    where:
    - SP: raw setpoint input (engineering units)
    - R: normalized setpoint output (0-100%)
    - hi, low: measurement range limits

    This system has no states and no dynamics - it's a pure gain
    (scaling function).

    Inputs: SP (setpoint in engineering units)
    Outputs: R (normalized setpoint 0-100%)
    """

    def __init__(self, name, hi, low, dt=0.1):
        # Validate parameters
        if hi <= low:
            raise ValueError(f'hi ({hi}) must be greater than low ({low})')

        self.params = {
            'name': str(name),
            'hi': float(hi),
            'low': float(low),
            'Ts': float(dt),
        }

        self.system = ct.NonlinearIOSystem(
            updfcn=None,
            outfcn=self.output,
            name=self.params['name'],
            outputs=['R'],
            inputs=['SP'],
            dt=self.params['Ts'],
        )

    def output(self, t, x, u, params):
        """Setpoint normalization: scale to 0-100% range.

        Parameters
        ----------
        t : float
            Current simulation time [s]
        x : array_like
            State vector (unused, no states in this system)
        u : array_like
            Input vector [SP] - setpoint in engineering units
        params : dict
            System parameters (unused, using self.params)

        Returns
        -------
        list
            Output vector [R] - normalized setpoint 0-100%
        """
        SP = float(u[0])
        hi = self.params['hi']
        low = self.params['low']

        # Linear scaling to 0-100% range
        if hi != low:
            R = (SP - low) / (hi - low) * 100.0
        else:
            R = 0.0

        return [R]

    def __repr__(self):
        return repr(self.system)
