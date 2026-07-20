import os
from typing import Any

import psutil


class ObservabilityTracker:
    """Tracks system and engine metrics (CPU, Memory, Queue Length)."""

    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge
        self.process = psutil.Process(os.getpid())
        # First call initializes the cpu_percent delta
        self.process.cpu_percent()

    def get_metrics(self) -> dict[str, str]:
        """Returns the latest metrics as formatted strings."""
        try:
            cpu = self.process.cpu_percent()
            mem = self.process.memory_info().rss / (1024 * 1024)
            # Fetch queue size safely
            queue_len = 0
            if hasattr(self.bridge, 'ipc') and hasattr(self.bridge.ipc, 'records'):
                queue_len = self.bridge.ipc.records.qsize()

            return {
                'cpu': f'{cpu:.1f}%',
                'mem': f'{mem:.1f} MB',
                'queue': f'{queue_len}',
            }
        except Exception:
            return {'cpu': 'N/A', 'mem': 'N/A', 'queue': 'N/A'}
