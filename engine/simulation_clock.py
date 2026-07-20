# engine/simulation_clock.py

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol


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
    quantum_seconds: float = 0.02,
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
    """

    if delay_seconds <= 0:
        return True

    deadline = time.perf_counter() + delay_seconds

    while True:
        if should_interrupt is not None and should_interrupt():
            return False

        remaining = deadline - time.perf_counter()

        if remaining <= 0:
            return True

        time.sleep(min(remaining, quantum_seconds))


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

        delay = self._next_tick - time.perf_counter()

        if delay <= 0:
            self._next_tick = time.perf_counter()
            time.sleep(self._min_yield_s)  # yield to UI thread (1A)
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

        delay = self._next_tick - time.perf_counter()

        if delay <= 0:
            self._next_tick = time.perf_counter()
            time.sleep(self._min_yield_s)  # yield to UI thread (1A)
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
