# models/controller.py

import control as ct
import numpy as np


class ControllerSystem:
    """PID process control system with anti-windup and derivative filtering.

    Implements a flexible PID controller that automatically switches
    between P, PI, PD, and PID modes based on tuning parameters.
    Includes:
    - Back-calculation anti-windup for integral action
    - Low-pass derivative filter to reduce noise sensitivity
    - Output saturation (clipping)
    - Support for direct and reverse control actions

    Parameters
    ----------
    name : str, optional
        Controller name for identification. Default: 'ControllerSystem'
    bias : float, optional
        Controller bias (setpoint) [%]. Required for P/PI mode.
        If None, uses 50.0 as default.
    mode : str, optional
        Control mode: 'AUTO' (auto-select based on Kc/tauI/tauD),
        'P', 'PI', 'PD', 'PID'. Default: 'AUTO'
    acting : str, optional
        Controller action: 'DIRECT' or 'REVERSE'. Default: 'REVERSE'

    Notes
    -----
    Controller automatically selects mode based on non-zero tuning parameters:
    - P only: tauI = 0, tauD = 0
    - PI: tauI > 0, tauD = 0
    - PD: tauI = 0, tauD > 0
    - PID: tauI > 0, tauD > 0

    Inputs: R (setpoint), C (process variable), Kc (gain),
    tauI (integral time), tauD (derivative time)
    Outputs: M (manipulated variable, 0-100%)
    States: I_state (integral), D_state (derivative filter)
    """

    # Control algorithm constants
    ALPHA_DERIVATIVE_FILTER = 0.125  # Derivative filter time constant ratio
    OUTPUT_MIN = 0.0  # Minimum output [%]
    OUTPUT_MAX = 100.0  # Maximum output [%]
    MODE_THRESHOLD = 1e-12  # Threshold for detecting zero tuning parameters

    def __init__(self, name='ControllerSystem', bias=None, mode='AUTO', acting='REVERSE', dt=0.1):
        # Validate control mode
        valid_modes = ['AUTO', 'P', 'PI', 'PD', 'PID']
        if mode not in valid_modes:
            raise ValueError(f'Invalid mode: {mode}. Must be one of {valid_modes}.')

        # Validate control action
        valid_acting = ['DIRECT', 'REVERSE']
        if acting not in valid_acting:
            raise ValueError(f'Invalid acting: {acting}. Must be one of {valid_acting}.')

        # Validate bias
        if bias is not None and (bias < self.OUTPUT_MIN or bias > self.OUTPUT_MAX):
            raise ValueError(f'Bias must be in range [0, 100], got {bias}')

        # Default bias to 50% if not specified
        bias = bias if bias is not None else 50.0

        self.params = {
            'name': str(name),
            'Alpha': float(self.ALPHA_DERIVATIVE_FILTER),
            'M_min': float(self.OUTPUT_MIN),
            'M_max': float(self.OUTPUT_MAX),
            'bias': float(bias),
            'mode': str(mode),
            'acting': str(acting),
            'dt': float(dt),
        }

        self.system = ct.NonlinearIOSystem(
            updfcn=self.update,
            outfcn=self.output,
            inputs=['R', 'C', 'Kc', 'tauI', 'tauD'],
            outputs=['M'],
            states=['I_state', 'D_state'],
            name=self.params['name'],
            dt=self.params['dt'],
        )

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_mode(tauI, tauD, params, eps=1e-12):
        """Determine active control mode from tuning parameters.

        Parameters
        ----------
        tauI : float
            Integral time constant [s]
        tauD : float
            Derivative time constant [s]
        params : dict
            Parameter dictionary with 'mode' key
        eps : float, optional
            Threshold for detecting zero parameters. Default: 1e-12

        Returns
        -------
        str
            Active mode: 'P', 'PI', 'PD', or 'PID'
        """
        forced = params['mode']
        if forced != 'AUTO':
            return forced

        has_I = float(tauI) > eps
        has_D = float(tauD) > eps

        if has_I and has_D:
            return 'PID'
        if has_I:
            return 'PI'
        if has_D:
            return 'PD'
        return 'P'

    def _P_controller(self, R, C, Kc, params):
        """Proportional (P) control law.

        Parameters
        ----------
        R : float
            Setpoint
        C : float
            Process variable
        Kc : float
            Proportional gain
        params : dict
            Parameter dictionary

        Returns
        -------
        tuple
            (dI_state, dD_state, M_sat) - derivative outputs and
            saturated control signal
        """
        M_min = self.params['M_min']
        M_max = self.params['M_max']
        Mo = self.params['bias']

        error = float(R) - float(C)
        Kc_eff = float(Kc) if self.params['acting'] == 'REVERSE' else -float(Kc)
        M_unsat = Mo + Kc_eff * error
        M_sat = float(np.clip(M_unsat, M_min, M_max))

        return 0.0, 0.0, M_sat

    def _PI_controller(self, R, C, Kc, tauI, I_state, params):
        """Proportional-Integral (PI) control law with anti-windup.

        Parameters
        ----------
        R : float
            Setpoint
        C : float
            Process variable
        Kc : float
            Proportional gain
        tauI : float
            Integral time constant [s]
        I_state : float
            Integral state accumulator
        params : dict
            Parameter dictionary

        Returns
        -------
        tuple
            (dI_state, dD_state, M_sat) - state derivatives and
            saturated output
        """
        M_min = self.params['M_min']
        M_max = self.params['M_max']

        error = float(R) - float(C)
        Kc_eff = float(Kc) if self.params['acting'] == 'REVERSE' else -float(Kc)
        M_unsat = Kc_eff * error + float(I_state)
        M_sat = float(np.clip(M_unsat, M_min, M_max))

        # Back-calculation anti-windup: adjust integrator for saturation
        dI_state = (Kc_eff / float(tauI)) * error + (M_sat - M_unsat) / float(tauI)

        return dI_state, 0.0, M_sat

    def _PD_controller(self, R, C, tauD, D_state, params):
        """Proportional-Derivative (PD) control law with filtering.

        Parameters
        ----------
        R : float
            Setpoint (not used in pure PD, included for consistency)
        C : float
            Process variable
        tauD : float
            Derivative time constant [s]
        D_state : float
            Derivative filter state
        params : dict
            Parameter dictionary

        Returns
        -------
        tuple
            (dI_state, dD_state, M_sat) - state derivatives and
            saturated output
        """
        M_min = self.params['M_min']
        M_max = self.params['M_max']
        Alpha = self.params['Alpha']

        diff = float(C) - float(D_state)

        # First-order low-pass filter for derivative action
        U = (1.0 / Alpha) * diff
        dD_state = U / float(tauD)

        M_unsat = float(C) + U
        M_sat = float(np.clip(M_unsat, M_min, M_max))

        return 0.0, dD_state, M_sat

    def _PID_controller(self, R, C, Kc, tauI, tauD, I_state, D_state, params):
        """Proportional-Integral-Derivative (PID) control law with
        filtering and anti-windup.

        Parameters
        ----------
        R : float
            Setpoint
        C : float
            Process variable
        Kc : float
            Proportional gain
        tauI : float
            Integral time constant [s]
        tauD : float
            Derivative time constant [s]
        I_state : float
            Integral accumulator state
        D_state : float
            Derivative filter state
        params : dict
            Parameter dictionary

        Returns
        -------
        tuple
            (dI_state, dD_state, M_sat) - state derivatives and
            saturated output
        """
        M_min = self.params['M_min']
        M_max = self.params['M_max']
        Alpha = self.params['Alpha']

        Kc_eff = float(Kc) if self.params['acting'] == 'REVERSE' else -float(Kc)

        diff = float(C) - float(D_state)

        # Derivative on PV only (not on error) to avoid derivative kick on
        # setpoint changes
        U_pd = (1.0 / Alpha) * diff
        dD_state = U_pd / float(tauD)

        # Filtered PV with derivative action
        C_filtered = float(C) + U_pd

        # Proportional and integral terms use filtered measurement
        error_filtered = float(R) - C_filtered
        M_unsat = Kc_eff * error_filtered + float(I_state)

        # Apply output saturation
        M_sat = float(np.clip(M_unsat, M_min, M_max))

        # Back-calculation anti-windup on integral term
        dI_state = (Kc_eff / float(tauI)) * error_filtered + (M_sat - M_unsat) / float(tauI)

        return dI_state, dD_state, M_sat

    # ------------------------------------------------------------------
    # ct.nlsys Interface Methods
    # ------------------------------------------------------------------

    def update(self, t, x, u, params):
        """
        DISCRETE-time state update for ct.nlsys with dt > 0:
        returns next state [I_state_next, D_state_next] instead of derivatives.
        """
        R, C, Kc, tauI, tauD = u
        I_state, D_state = x

        dt = self.params['dt']
        Alpha = self.params['Alpha']

        local_params = self.params
        mode = self._resolve_mode(tauI, tauD, local_params, self.MODE_THRESHOLD)

        # Default: hold states
        I_next = float(I_state)
        D_next = float(D_state)

        # --- P mode: no state dynamics ---
        if mode == 'P':
            return [I_next, D_next]

        # --- PI mode: discretize integrator (Euler), hold derivative state ---
        if mode == 'PI':
            dI, _, _ = self._PI_controller(R, C, Kc, tauI, I_state, local_params)
            I_next = float(I_state) + dt * float(dI)
            return [I_next, D_next]

        # --- PD mode: hold integrator, discretize derivative filter state ---
        if mode == 'PD':
            # Your continuous filter is:
            # dD/dt = (C - D) / (Alpha * tauD)
            # Exact ZOH discretization for constant C over sample:
            # D[k+1] = a*D[k] + (1-a)*C[k],  a = exp(-dt/(Alpha*tauD))
            tauD_eff = float(tauD)
            if tauD_eff > self.MODE_THRESHOLD:
                a = np.exp(-dt / (Alpha * tauD_eff))
                D_next = a * float(D_state) + (1.0 - a) * float(C)
            # else: if tauD ~ 0, hold D_state
            return [I_next, D_next]

        # --- PID mode: discretize integrator (Euler) + derivative
        # filter (exact) ---
        if mode == 'PID':
            dI, _, _ = self._PID_controller(R, C, Kc, tauI, tauD, I_state, D_state, local_params)
            I_next = float(I_state) + dt * float(dI)

            tauD_eff = float(tauD)
            if tauD_eff > self.MODE_THRESHOLD:
                a = np.exp(-dt / (Alpha * tauD_eff))
                D_next = a * float(D_state) + (1.0 - a) * float(C)

            return [I_next, D_next]

        raise ValueError(f"[{local_params['name']}] Unknown controller mode: '{mode}'")

    def output(self, t, x, u, params):
        """Output equation for ct.nlsys.

        Parameters
        ----------
        t : float
            Current simulation time [s]
        x : array_like
            State vector [I_state, D_state]
        u : array_like
            Input vector [R, C, Kc, tauI, tauD]
        params : dict
            System parameters (unused, using self.params)

        Returns
        -------
        list
            Output vector [M] - manipulated variable (0-100%)
        """
        R, C, Kc, tauI, tauD = u
        I_state, D_state = x

        local_params = self.params
        mode = self._resolve_mode(tauI, tauD, local_params, self.MODE_THRESHOLD)

        if mode == 'P':
            _, _, M_sat = self._P_controller(R, C, Kc, local_params)
        elif mode == 'PI':
            _, _, M_sat = self._PI_controller(R, C, Kc, tauI, I_state, local_params)
        elif mode == 'PD':
            _, _, M_sat = self._PD_controller(R, C, tauD, D_state, local_params)
        elif mode == 'PID':
            _, _, M_sat = self._PID_controller(R, C, Kc, tauI, tauD, I_state, D_state, local_params)
        else:
            raise ValueError(f"[{local_params['name']}] Unknown controller mode: '{mode}'")

        return [M_sat]

    def __repr__(self):
        return repr(self.system)
