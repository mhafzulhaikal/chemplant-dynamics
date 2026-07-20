# models/plant.py

import control as ct
import numpy as np
from scipy.integrate import solve_ivp

from models.base import PlantSystemBase


class BiodieselReactorSystem(PlantSystemBase):
    plant_name = 'biodiesel'
    default_time_unit = 'seconds'

    def __init__(
        self,
        rho_oil,
        Cp_oil,
        rho_MeOH,
        Cp_MeOH,
        rho_NaOH,
        Cp_NaOH,
        rho,
        Cp,
        Dr,
        Lr,
        R,
        To,
        Hrxn1,
        Hrxn2,
        Hrxn3,
        k1_f,
        k1_r,
        k2_f,
        k2_r,
        k3_f,
        k3_r,
        E1_f,
        E1_r,
        E2_f,
        E2_r,
        E3_f,
        E3_r,
        UA,
        V_coolant,
        rho_coolant,
        Cp_coolant,
        dt=0.5,  # <-- sample time [s]
        rtol=1e-6,
        atol=1e-9,  # <-- solver tolerances
    ):
        self.dt = float(dt)
        self.rtol = rtol
        self.atol = atol

        self.params = {
            # oil stream properties
            'rho_oil': rho_oil,
            'Cp_oil': Cp_oil,
            # methanol stream properties
            'rho_MeOH': rho_MeOH,
            'Cp_MeOH': Cp_MeOH,
            # catalyst stream properties
            'rho_NaOH': rho_NaOH,
            'Cp_NaOH': Cp_NaOH,
            # product stream properties
            'rho': rho,
            'Cp': Cp,
            # reactor parameters
            'Dr': Dr,
            'Lr': Lr,
            'Ar': (np.pi * Dr**2 / 4),
            # reaction parameters
            'R': R,
            'To': To,
            'Hrxn1': Hrxn1,
            'Hrxn2': Hrxn2,
            'Hrxn3': Hrxn3,
            # kinetic parameters
            'k1_f': k1_f,
            'k1_r': k1_r,
            'k2_f': k2_f,
            'k2_r': k2_r,
            'k3_f': k3_f,
            'k3_r': k3_r,
            'E1_f': E1_f,
            'E1_r': E1_r,
            'E2_f': E2_f,
            'E2_r': E2_r,
            'E3_f': E3_f,
            'E3_r': E3_r,
            # heat transfer parameters
            'UA': UA,
            'V_coolant': V_coolant,
            # cooling fluid properties
            'rho_coolant': rho_coolant,
            'Cp_coolant': Cp_coolant,
        }

        # 13 inputs: 8 process disturbances + 5 manipulated valve commands
        inputs = [
            'c_TG_in',
            'T_oil',
            'c_MeOH_in',
            'T_MeOH',
            'c_Cat_in',
            'c_Water_in',
            'T_NaOH',
            'T_coolant_in',
            'f_oil',
            'f_MeOH',
            'f_NaOH',
            'f_FAME',
            'f_coolant',
        ]

        # 11 states
        states = [
            'h',
            'c_TG',
            'c_MeOH',
            'c_ME',
            'c_DG',
            'c_MG',
            'c_Gly',
            'c_Cat',
            'c_Water',
            'T',
            'T_coolant',
        ]

        outputs = states.copy()

        # ✅ Set dt=self.Ts to declare a discrete-time I/O system
        self.system = ct.NonlinearIOSystem(
            updfcn=self.update,  # returns x[k+1] for discrete time
            outfcn=self.output,
            inputs=inputs,
            outputs=outputs,
            states=states,
            name='biodiesel_reactor',
            dt=self.dt,
        )

    # ---------- continuous-time RHS: dx/dt = f(t, x, u) ----------
    def rhs(self, t, x, u):
        # ---------- state unpack (11) ----------
        (h, c_TG, c_MeOH, c_ME, c_DG, c_MG, c_Gly, c_Cat, c_Water, T, T_coolant) = x

        # ---------- input unpack (13) ----------
        (
            c_TG_in,
            T_oil,
            c_MeOH_in,
            T_MeOH,
            c_Cat_in,
            c_Water_in,
            T_NaOH,
            T_coolant_in,
            f_oil,
            f_MeOH,
            f_NaOH,
            f_FAME,
            f_coolant,
        ) = u

        # ---------- parameter access ----------
        p = self.params

        # ---------- safeguards ----------
        h_eff = max(h, 1e-8)
        T_eff = max(T, 1.0)

        # ---------- pre-computed factors ----------
        volume = p['Ar'] * h_eff
        volume_inv = 1.0 / volume
        inflow_mass = (f_oil * p['rho_oil']) + (f_MeOH * p['rho_MeOH']) + (f_NaOH * p['rho_NaOH'])
        inflow = inflow_mass / p['rho']
        arrhenius_factor = (1.0 / p['To']) - (1.0 / T_eff)

        # ---------- kinetics ----------
        exp_1f = np.exp((p['E1_f'] / p['R']) * arrhenius_factor)
        exp_1r = np.exp((p['E1_r'] / p['R']) * arrhenius_factor)
        exp_2f = np.exp((p['E2_f'] / p['R']) * arrhenius_factor)
        exp_2r = np.exp((p['E2_r'] / p['R']) * arrhenius_factor)
        exp_3f = np.exp((p['E3_f'] / p['R']) * arrhenius_factor)
        exp_3r = np.exp((p['E3_r'] / p['R']) * arrhenius_factor)

        r1 = (p['k1_f'] * exp_1f * c_TG * c_MeOH * c_Cat) - (p['k1_r'] * exp_1r * c_ME * c_DG)
        r2 = (p['k2_f'] * exp_2f * c_DG * c_MeOH * c_Cat) - (p['k2_r'] * exp_2r * c_ME * c_MG)
        r3 = (p['k3_f'] * exp_3f * c_MG * c_MeOH * c_Cat) - (p['k3_r'] * exp_3r * c_ME * c_Gly)

        # ---------- level ----------
        dh_dt = (1.0 / (p['rho'] * p['Ar'])) * (inflow_mass - (f_FAME * p['rho']))

        # ---------- concentrations ----------
        dc_TG_dt = volume_inv * ((f_oil * c_TG_in) - (inflow * c_TG) - (p['Ar'] * h_eff * r1))
        dc_MeOH_dt = volume_inv * (
            (f_MeOH * c_MeOH_in) - (inflow * c_MeOH) - (p['Ar'] * h_eff * (r1 + r2 + r3))
        )
        dc_ME_dt = volume_inv * ((p['Ar'] * h_eff * (r1 + r2 + r3)) - (inflow * c_ME))
        dc_DG_dt = volume_inv * ((p['Ar'] * h_eff * (r1 - r2)) - (inflow * c_DG))
        dc_MG_dt = volume_inv * ((p['Ar'] * h_eff * (r2 - r3)) - (inflow * c_MG))
        dc_Gly_dt = volume_inv * ((p['Ar'] * h_eff * r3) - (inflow * c_Gly))
        dc_Cat_dt = volume_inv * ((f_NaOH * c_Cat_in) - (inflow * c_Cat))
        dc_Water_dt = volume_inv * ((f_NaOH * c_Water_in) - (inflow * c_Water))

        # ---------- temperatures ----------
        dT_dt = (1.0 / (p['Ar'] * p['rho'] * p['Cp'] * h_eff)) * (
            (
                (f_oil * p['rho_oil'] * p['Cp_oil'] * T_oil)
                + (f_MeOH * p['rho_MeOH'] * p['Cp_MeOH'] * T_MeOH)
                + (f_NaOH * p['rho_NaOH'] * p['Cp_NaOH'] * T_NaOH)
            )
            - (p['UA'] * (T_eff - T_coolant))
            - (inflow_mass * p['Cp'] * T_eff)
            - (p['Ar'] * h_eff * (r1 * p['Hrxn1'] + r2 * p['Hrxn2'] + r3 * p['Hrxn3']))
        )

        dT_coolant_dt = (1.0 / (p['V_coolant'] * p['rho_coolant'] * p['Cp_coolant'])) * (
            (f_coolant * p['rho_coolant'] * p['Cp_coolant'] * T_coolant_in)
            + (p['UA'] * (T_eff - T_coolant))
            - (f_coolant * p['rho_coolant'] * p['Cp_coolant'] * T_coolant)
        )

        return np.array(
            [
                dh_dt,
                dc_TG_dt,
                dc_MeOH_dt,
                dc_ME_dt,
                dc_DG_dt,
                dc_MG_dt,
                dc_Gly_dt,
                dc_Cat_dt,
                dc_Water_dt,
                dT_dt,
                dT_coolant_dt,
            ],
            dtype=float,
        )

    # ---------- DISCRETE update: x[k+1] = Integrate RHS over one sample using
    def update(self, t, x, u, params):
        dt = self.dt
        x0 = np.asarray(x, dtype=float)
        u0 = np.asarray(u, dtype=float)  # zero-order hold input over [t, t+Ts]

        def fun(tau, x_tau):
            return self.rhs(tau, x_tau, u0)

        # Integrate one interval; store solution at exactly t+Ts
        sol = solve_ivp(
            fun,
            (float(t), float(t + dt)),  # t_span
            x0,
            method='LSODA',  # LSODA available in solve_ivp
            t_eval=[float(t + dt)],  # evaluate at end of interval
            rtol=self.rtol,
            atol=self.atol,
            max_step=dt,  # optional cap; LSODA still adaptive within this
        )

        if not sol.success:
            raise RuntimeError(f'LSODA failed at t={t}: {sol.message}')

        x_next = sol.y[:, -1]  # state at t+dt from t_eval output
        return x_next  # discrete-time updfcn returns next state

    def output(self, t, x, u, params):
        return np.asarray(x)

    def __repr__(self):
        return repr(self.system)

    def default_state(self):
        # Default x0 is zero-state unless a case/session provides a better
        # seed.
        return [0.0] * int(getattr(self.system, 'nstates', 0))


# STHR SYSTEM (DISCRETE-TIME via LSODA inside update)
class STHRSystem(PlantSystemBase):
    plant_name = 'sthr'
    default_time_unit = 'minutes'

    def __init__(self, rho=68.0, Cp=0.80, V=120.0, A=241.5, Cm=265.68, U=2.1, lamb=966.0, dt=0.5):
        self.dt = float(dt)  # sample time [min]
        self.rtol = 1e-6
        self.atol = 1e-9

        self.params = {
            'rho': rho,
            'Cp': Cp,
            'V': V,
            'A': A,
            'Cm': Cm,
            'U': U,
            'lamb': lamb,
        }

        inputs = ['F', 'Ti', 'W']
        states = ['T', 'Ts']
        outputs = states.copy()

        self.system = ct.NonlinearIOSystem(
            updfcn=self.update,  # returns x[k+1] for discrete time
            outfcn=self.output,
            inputs=inputs,
            outputs=outputs,
            states=states,
            name='STHR',
            dt=self.dt,
        )

    def rhs(self, t, x, u):
        T, Ts = x
        F, Ti, W = u

        p = self.params

        dTdt = (F / p['V']) * (Ti - T) + (p['U'] * p['A'] / (p['V'] * p['rho'] * p['Cp'])) * (
            Ts - T
        )
        dTsdt = (1 / p['Cm']) * (p['lamb'] * W - p['U'] * p['A'] * (Ts - T))

        return np.array([dTdt, dTsdt], dtype=float)

    def update(self, t, x, u, params):
        dt = self.dt
        x0 = np.asarray(x, dtype=float)
        u0 = np.asarray(u, dtype=float)  # zero-order hold input over [t, t+dt]

        def fun(tau, x_tau):
            return self.rhs(tau, x_tau, u0)

        sol = solve_ivp(
            fun,
            (float(t), float(t + dt)),  # t_span
            x0,
            method='LSODA',  # LSODA available in solve_ivp
            t_eval=[float(t + dt)],  # evaluate at end of interval
            rtol=self.rtol,
            atol=self.atol,
            max_step=dt,  # optional cap; LSODA still adaptive within this
        )

        if not sol.success:
            raise RuntimeError(f'LSODA failed at t={t}: {sol.message}')

        x_next = sol.y[:, -1]  # state at t+dt from t_eval output
        return x_next  # discrete-time updfcn returns next state

    def output(self, t, x, u, params):
        return np.asarray(x)

    def __repr__(self):
        return repr(self.system)

    def default_state(self):
        # Existing runtime baseline for STHR process states.
        return [150.0, 230.0]
