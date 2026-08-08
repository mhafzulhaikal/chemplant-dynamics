# engine/simulation_clock.py

from __future__ import annotations

import ctypes
import sys
import time
from collections.abc import Callable
from typing import Protocol

# Detect Pyodide (browser WebAssembly) environment.
_IS_PYODIDE: bool = (
    hasattr(sys, '_emscripten_info') or sys.platform == 'emscripten' or 'pyodide' in sys.modules
)

# ---------------------------------------------------------------------------
# Windows Multimedia Timer — high-resolution mode
# ---------------------------------------------------------------------------
# On Windows, the default OS scheduler quantum is ~15.6 ms.  Calling
# timeBeginPeriod(1) asks the kernel to use 1 ms quanta for the lifetime of
# this process, which lets time.sleep() honour sub-10 ms delays accurately.
# This is the same technique used by audio workstations and game engines.
# We activate it once at import time and leave it on for the process lifetime.
# ---------------------------------------------------------------------------

_winmm: ctypes.WinDLL | None = None

if sys.platform == 'win32' and not _IS_PYODIDE:
    try:
        _winmm = ctypes.windll.winmm  # type: ignore[attr-defined]
        _winmm.timeBeginPeriod(1)
    except Exception:
        _winmm = None


class SimulationClock(Protocol):
    """
    Interface clock simulasi.

    Clock hanya bertanggung jawab untuk pacing/waktu tunggu antar step.
    Engine/session tidak perlu tahu apakah simulasi real-time atau accelerated.
    """

    def reset(self) -> None: ...

    def wait_next_step(
        self,
        Ts_minutes: float,
        *,
        should_interrupt: Callable[[], bool] | None = None,
    ) -> bool: ...


def _interruptible_sleep(
    delay_seconds: float,
    *,
    should_interrupt: Callable[[], bool] | None = None,
    quantum_seconds: float = 0.002,
) -> bool:
    """
    Sleep yang bisa diputus oleh:
        - perubahan config
        - restart
        - stop

    Return:
        True:
            sleep selesai normal, step boleh dijalankan.

        False:
            sleep diputus, loop harus membaca ulang config.

    With timeBeginPeriod(1) active, quantum_seconds=2ms gives us OS-level
    precision without burning CPU in a tight spin loop.
    """
    # In Pyodide, blocking sleep is a no-op; the async clock handles pacing.
    if _IS_PYODIDE:
        return True

    if delay_seconds <= 0:
        return True

    deadline = time.perf_counter() + delay_seconds

    # Hybrid sleep: sleep in chunks until within SPIN_THRESHOLD of deadline,
    # then busy-wait for the final stretch.  With timeBeginPeriod(1) the OS
    # wakes us reliably within ~1ms, so SPIN_THRESHOLD can be tight (1ms).
    SPIN_THRESHOLD = 0.001

    while True:
        if should_interrupt is not None and should_interrupt():
            return False

        remaining = deadline - time.perf_counter()

        if remaining <= 0:
            return True

        if remaining > SPIN_THRESHOLD:
            # Sleep up to one OS quantum, capped so we stay interruptible.
            time.sleep(min(remaining - SPIN_THRESHOLD, quantum_seconds))
        # else: busy-spin the last <1ms for microsecond accuracy


class RealTimeClock:
    """
    Clock untuk real_time=True.

    Aturan:
        1 menit waktu simulasi = 1 menit waktu nyata.

    Catatan:
        acceleration diabaikan.
    """

    def __init__(self) -> None:
        self._next_tick = time.perf_counter()
        # 1 ms minimum yield when behind schedule
        self._min_yield_s: float = 0.001
        self._max_debt_s: float = 0.5  # Max 500ms debt before resetting

    def reset(self) -> None:
        self._next_tick = time.perf_counter()

    def wait_next_step(
        self,
        Ts_minutes: float,
        *,
        should_interrupt: Callable[[], bool] | None = None,
    ) -> bool:
        period_seconds = max(float(Ts_minutes), 0.0) * 60.0

        self._next_tick += period_seconds

        now = time.perf_counter()
        delay = self._next_tick - now

        if delay <= 0:
            # We are falling behind. Check if debt exceeded the ceiling.
            debt = -delay
            if debt > self._max_debt_s:
                # Debt too large (e.g. system suspended or heavy lag), reset clock
                self._next_tick = now

            # Yield minimally so the UI thread doesn't completely freeze
            time.sleep(self._min_yield_s)
            return True

        completed = _interruptible_sleep(
            delay,
            should_interrupt=should_interrupt,
        )

        if not completed:
            self._next_tick = time.perf_counter()

        return completed


class AcceleratedClock:
    """
    Clock untuk real_time=False.

    Definisi acceleration:
        acceleration = 1
            setara real-time

        acceleration > 1
            lebih cepat

        acceleration < 1
            lebih lambat

    Formula:
        wall_delay = Ts_seconds / acceleration

    Contoh:
        Ts = 0.01 menit = 0.6 detik

        acceleration = 1
            delay = 0.6 detik

        acceleration = 2
            delay = 0.3 detik

        acceleration = 0.1
            delay = 6.0 detik

        acceleration = 0.01
            delay = 60.0 detik
    """

    def __init__(self, acceleration: float) -> None:
        self.acceleration = max(float(acceleration), 1e-12)
        self._next_tick = time.perf_counter()
        # 1 ms minimum yield when behind schedule
        self._min_yield_s: float = 0.001
        self._max_debt_s: float = 0.5

    def reset(self) -> None:
        self._next_tick = time.perf_counter()

    def wait_next_step(
        self,
        Ts_minutes: float,
        *,
        should_interrupt: Callable[[], bool] | None = None,
    ) -> bool:
        sim_period_seconds = max(float(Ts_minutes), 0.0) * 60.0
        wall_period_seconds = sim_period_seconds / self.acceleration

        self._next_tick += wall_period_seconds

        now = time.perf_counter()
        delay = self._next_tick - now

        if delay <= 0:
            debt = -delay
            if debt > self._max_debt_s:
                self._next_tick = now

            time.sleep(self._min_yield_s)
            return True

        completed = _interruptible_sleep(
            delay,
            should_interrupt=should_interrupt,
        )

        if not completed:
            self._next_tick = time.perf_counter()

        return completed


def make_clock(
    *,
    real_time: bool,
    acceleration: float,
) -> SimulationClock:
    """
    Factory clock.

    Aturan:
        real_time=True:
            RealTimeClock.
            acceleration diabaikan.

        real_time=False:
            AcceleratedClock.
            acceleration menentukan speed.
    """

    if real_time:
        return RealTimeClock()

    return AcceleratedClock(acceleration=acceleration)
