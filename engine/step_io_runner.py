# engine/step_io_runner.py

from collections.abc import Sequence
from typing import Any

import numpy as np


class StepInputOutputRunner:
    """
    Step-by-step runtime runner for python-control NonlinearIOSystem /
    InterconnectedSystem.

    This runner is intended as a streaming/runtime alternative to
    ct.input_output_response.

    It does NOT call ct.input_output_response.

    It directly uses:
        y[k]     = sys._out(t, x[k], u[k])
        x[k+1]   = sys._rhs(t, x[k], u[k])

    This is suitable for your current systems because your subsystems are
    discrete-time NonlinearIOSystem objects whose update functions return
    x[k+1], not dx/dt.

    Parameters
    ----------
    sys:
        A python-control NonlinearIOSystem or InterconnectedSystem.

    dt:
        Sampling time. If None, uses sys.dt.

    x0:
        Initial state vector. Can be scalar, list, tuple, or np.ndarray.

    input_labels:
        Labels for external inputs. If None, uses sys.input_labels.

    output_labels:
        Labels for outputs. If None, uses sys.output_labels.

    params:
        Optional parameter dictionary passed to sys._update_params.

    t0:
        Initial time.

    output_timing:
        "pre":
            Return output before state update:
                y[k] = output(x[k], u[k])
                x[k+1] = update(x[k], u[k])

            This matches python-control discrete-time response convention.

        "post":
            Return output after state update:
                x[k+1] = update(x[k], u[k])
                y[k+1] = output(x[k+1], u[k])
    """

    def __init__(
        self,
        sys,
        dt: float | None = None,
        x0: float | Sequence[float] | np.ndarray = 0.0,
        input_labels: Sequence[str] | None = None,
        output_labels: Sequence[str] | None = None,
        params: dict[str, Any] | None = None,
        t0: float = 0.0,
        output_timing: str = 'pre',
    ):
        self.sys = sys
        self.t = float(t0)

        dt_source = dt if dt is not None else getattr(sys, 'dt', None)
        if dt_source is None:
            raise ValueError('StepInputOutputRunner requires a discrete sample time dt.')

        self.dt = float(dt_source)

        if output_timing not in ('pre', 'post'):
            raise ValueError("output_timing must be either 'pre' or 'post'.")

        self.output_timing = output_timing

        resolved_input_labels = (
            input_labels if input_labels is not None else getattr(sys, 'input_labels', None)
        )
        resolved_output_labels = (
            output_labels if output_labels is not None else getattr(sys, 'output_labels', None)
        )

        self.input_labels = list(resolved_input_labels or [])
        self.output_labels = list(resolved_output_labels or [])

        self.params = params or {}

        # Update system params once
        if hasattr(self.sys, '_update_params'):
            self.sys._update_params(self.params)

        # Internal state
        self.x = self._process_x0(x0)

        # Cache last input and output
        self._last_u = np.zeros(len(self.input_labels), dtype=float)
        self._y = dict.fromkeys(self.output_labels, 0.0)

        # Initialize output from initial state
        self._compute_and_cache_output(self.t, self.x, self._last_u)

    # ==========================================================
    # Utilities
    # ==========================================================
    def _process_x0(self, x0: float | Sequence[float] | np.ndarray) -> np.ndarray:
        """
        Convert x0 to vector of length sys.nstates.
        Pads with zeros if x0 is shorter than nstates.
        Raises if x0 is longer than nstates.
        """

        nstates = int(self.sys.nstates or 0)

        x = np.asarray(x0, dtype=float).reshape(-1)

        if x.size < nstates:
            x_pad = np.zeros(nstates, dtype=float)
            x_pad[: x.size] = x
            return x_pad

        if x.size > nstates:
            raise ValueError(f'X0 has too many states: got {x.size}, expected {nstates}')

        return x.copy()

    def _u_dict_to_vector(self, u_dict: dict[str, float]) -> np.ndarray:
        """
        Convert external input dictionary into vector using input_labels order.
        Reuses a pre-allocated buffer to avoid per-step allocation.
        """

        for i, label in enumerate(self.input_labels):
            self._last_u[i] = float(u_dict.get(label, 0.0))
        return self._last_u

    def _compute_and_cache_output(self, t: float, x: np.ndarray, u_vec: np.ndarray):
        """
        Compute y = sys._out(t, x, u) and cache as dict.
        """

        y_vec = np.asarray(self.sys._out(t, x, u_vec), dtype=float).reshape(-1)

        if len(y_vec) != len(self.output_labels):
            raise RuntimeError(
                f'Output size mismatch: got {len(y_vec)}, expected {len(self.output_labels)}'
            )

        for i in range(len(self.output_labels)):
            self._y[self.output_labels[i]] = float(y_vec[i])

        return self._y

    # ==========================================================
    # Main runtime API
    # ==========================================================
    def step(self, u_dict: dict[str, float] | None = None):
        """
        Run one simulation step.

        Parameters
        ----------
        u_dict:
            External input dictionary using full signal names.

            Example:
                {
                    "TSP-100.SP": 150.0,
                    "TC-100.Kc": 6.1,
                    "TC-100.tauI": 2.3,
                    "TC-100.tauD": 0.58,
                    "STHR.F": 15.0,
                    "STHR.Ti": 100.0,
                }

        Returns
        -------
        dict
            Output dictionary using output_labels.
        """

        if u_dict is None:
            u_dict = {}

        u_vec = self._u_dict_to_vector(u_dict)

        # ------------------------------------------------------
        # PRE-output mode
        # ------------------------------------------------------
        if self.output_timing == 'pre':
            self._compute_and_cache_output(self.t, self.x, u_vec)

            if self.sys.nstates and self.sys.nstates > 0:
                x_next = self.sys._rhs(self.t, self.x, u_vec)
                self.x = np.asarray(x_next, dtype=float).reshape(-1)

            self.t += self.dt
            return self._y

        # ------------------------------------------------------
        # POST-output mode
        # ------------------------------------------------------
        if self.sys.nstates and self.sys.nstates > 0:
            x_next = self.sys._rhs(self.t, self.x, u_vec)
            self.x = np.asarray(x_next, dtype=float).reshape(-1)

            if self.x.size != int(self.sys.nstates):
                raise RuntimeError(
                    f'State size mismatch: got {self.x.size}, expected {int(self.sys.nstates)}'
                )

        self.t += self.dt

        self._compute_and_cache_output(self.t, self.x, u_vec)
        return self._y

    def output(self):
        return dict(self._y)

    def state(self):
        return self.x.copy()

    def time(self):
        return self.t

    def reset(
        self,
        x0: float | Sequence[float] | np.ndarray | None = None,
        t0: float = 0.0,
    ):
        """
        Reset runner state.
        """

        self.t = float(t0)

        if x0 is not None:
            self.x = self._process_x0(x0)

        self._compute_and_cache_output(self.t, self.x, self._last_u)
