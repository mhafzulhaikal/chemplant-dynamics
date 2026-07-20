# gateway/core/bridge_ipc.py

"""Inter-thread communication boundaries for the Bridge.

Encapsulates the queues, locks, and events used to communicate
between the main UI thread and the SimulationWorker thread.
"""

from __future__ import annotations

import logging
from queue import Empty, Full, Queue
from threading import Event, Lock

from gateway.core.bridge_support import BridgeRecord

logger = logging.getLogger(__name__)


class BridgeIPC:
    """Manages thread-safe communication channels for the Bridge.

    Owns the record queues and the lifecycle control events
    (pause, stop, restart, config_change).
    """

    def __init__(self, maxsize: int = 200) -> None:
        self.lock = Lock()
        # UI rendering queue (fast drain)
        self.records: Queue[BridgeRecord] = Queue(maxsize=maxsize)
        # Headless / data logger queue (slower drain, needs higher capacity but must be bounded)
        self.log_records: Queue[BridgeRecord] = Queue(maxsize=1000)

        self.stop_event = Event()
        self.pause_event = Event()
        self.restart_event = Event()
        self.config_changed_event = Event()

    def put_record(self, record: BridgeRecord) -> None:
        """Push a record to the UI queue.

        If the queue is full (e.g. engine is far outpacing UI rendering),
        the oldest record is dropped to make room. This prioritizes live
        current data over a perfect backlog.
        """
        try:
            self.records.put_nowait(record)
        except Full:
            try:
                self.records.get_nowait()
            except Empty:
                pass
            try:
                self.records.put_nowait(record)
            except Full:
                pass

        if record.kind in ('status', 'header', 'step'):
            self.put_log_only(record)

    def put_log_only(self, record: BridgeRecord) -> None:
        """Push a record exclusively to the log queue with overflow drop."""
        try:
            self.log_records.put_nowait(record)
        except Full:
            try:
                self.log_records.get_nowait()
            except Empty:
                pass
            try:
                self.log_records.put_nowait(record)
            except Full:
                pass

    def drain_records(self, max_records: int = 300) -> list[BridgeRecord]:
        """Drain up to `max_records` from the primary records queue."""
        out: list[BridgeRecord] = []
        while len(out) < max_records:
            try:
                out.append(self.records.get_nowait())
            except Empty:
                break
        return out

    def drain_log_records(self, max_records: int = 300) -> list[BridgeRecord]:
        """Drain up to `max_records` from the dedicated log queue."""
        out: list[BridgeRecord] = []
        while len(out) < max_records:
            try:
                out.append(self.log_records.get_nowait())
            except Empty:
                break
        return out

    def clear_queues(self) -> None:
        """Aggressively empty both internal record queues."""
        try:
            while True:
                self.records.get_nowait()
        except Empty:
            pass

        try:
            while True:
                self.log_records.get_nowait()
        except Empty:
            pass

    def signal_stop(self) -> None:
        self.stop_event.set()

    def signal_pause(self) -> None:
        self.pause_event.set()

    def signal_resume(self) -> None:
        self.pause_event.clear()

    def signal_restart(self) -> None:
        self.restart_event.set()

    def signal_config_change(self) -> None:
        self.config_changed_event.set()

    def is_paused(self) -> bool:
        return self.pause_event.is_set()

    def is_stopped(self) -> bool:
        return self.stop_event.is_set()
