# app/hub/signal_hub.py

"""Parent hub: single-producer / multi-subscriber fan-out.

Architecture (see ``README.md`` section "SignalHub (parent–child
broadcast, v2)" for the high-level picture):

::

        ENGINE → bridge._records (Queue)        ──── 1× per-page producer
                       │
                       ▼   (drain once per tick)
            ┌──────────────────────────────┐
            │   SignalHub  (PARENT)        │
            │  - snapshot, lock            │
            │  - subscribers: [Child, ...] │
            │  - 1× ui.timer @ tick_s      │
            └──────────────────────────────┘
              │      │      │      │
              ▼      ▼      ▼      ▼
            SvgChild Faceplate Modal Logger ...

Properties this delivers:

- **No queue race.** Only ``SignalHub._tick`` calls
  ``bridge.drain_records()``. Children NEVER touch the queue.
- **Same value, same tick.** A single ``_tick`` builds one
  ``snapshot`` and one ``delta_keys`` set, then dispatches them
  *sequentially in the same Python turn* to every child — so
  "one number from the engine appears at every child in the same
  tick" is structural, not just best-effort.
- **Bidirectional channel.** ``request_write(modal_key, value)``
  resolves to the engine tag and either:
    * sets ``bridge.state.input_overrides[engine_tag]`` (writable
      input), or
    * routes a status key change through
      ``bridge.apply_runtime_configuration(restart_if_needed=True)``.
  The engine's echo lands in the next ``_run_one_step`` record
  and is fanned out to *all* children — so a SP edit in the modal
  is reflected in the SVG, faceplate, data logger, and chart in
  the same downstream tick.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from app.hub.controller_registry import ControllerRegistry
from app.hub.engine_adapter import (
    EngineBridgeAdapter,
    TickMeta,
    mode_code_to_name,
    mode_name_to_code,
)
from app.hub.engine_control import EngineControl

logger = logging.getLogger(__name__)


def _offload(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run ``func(*args, **kwargs)`` in the default thread pool so the UI/main
    thread is not blocked by I/O or CPU work that does not touch NiceGUI
    elements directly."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        loop.run_in_executor(None, lambda: func(*args, **kwargs))
    except Exception:
        pass


class Subscriber(Protocol):
    """Anything the hub can fan out to."""

    def on_tick(
        self,
        delta_keys: frozenset[str],
        snapshot: Mapping[str, float],
        meta: TickMeta,
    ) -> None: ...


class SignalHub:
    """Parent broadcast hub.

    One per page, per case. Wraps the per-browser bridge and the
    case's :class:`ControllerRegistry`. Spins a SINGLE ``ui.timer``
    at ``tick_s`` (default 50 ms = 20 Hz) — this is the only timer
    that ever calls ``bridge.drain_records()``.

    See :func:`build_sthr_hub` and :func:`build_biodiesel_hub` for
    construction helpers.
    """

    def __init__(
        self,
        bridge: Any,
        registry: ControllerRegistry,
        *,
        initial: Mapping[str, float] | None = None,
        tick_s: float = 0.05,
    ) -> None:
        self._bridge = bridge
        self._registry = registry
        self._tick_s = float(tick_s)
        self._engine_control = EngineControl(bridge)

        from app.hub.ui_sync_manager import UiSyncManager

        self.ui_sync = UiSyncManager(registry)

        self._lock = threading.Lock()
        self._snapshot: dict[str, float] = dict(initial or {})
        # modal_key -> expiration timestamp
        self._write_locks: dict[str, float] = {}
        self._local_dirty_keys: set[str] = set()
        # Initial seed snapshot used by ``reset()`` to repopulate the
        # cache so a child reading immediately after reset still sees
        # the case-config baseline (matches legacy
        # ``BaseBridgeStore._initial_seed``).
        self._initial_seed: dict[str, float] = dict(initial or {})

        # Subscribers — stored as a tuple snapshot so iteration during
        # ``_tick`` can drop the lock as soon as the snapshot is taken.
        self._subscribers: list[Subscriber] = []

        # Cache registry lookups — these maps are immutable after
        # construction so we cache them once rather than calling
        # the registry methods on every tick.
        output_to_pv = registry.output_to_pv()
        input_map = registry.input_field_to_override()
        status_keys = registry.status_keys()
        self._derived_pairs = registry.derived_pairs()

        # Instantiate the pure python EngineBridgeAdapter
        self._adapter = EngineBridgeAdapter(bridge, output_to_pv, input_map, status_keys)

        # Monotonic tick counter — exposed to the client store so
        # out-of-order batches under on_air jitter can be ignored.
        self._tick_counter: int = 0
        self._reset_counter: int = 0

        # Adaptive drain cap — self-tunes based on tick wall time (2A).
        # Starts at 20; halves when tick > tick_s, doubles when < tick_s/2.
        # Clamped to [1, 40].
        self._drain_cap: int = 20

        # NiceGUI timer handle so ``stop()`` can cancel it.
        self._timer: Any = None

        # Historical buffers for UI charts/logs
        self._history: deque[dict] = deque(maxlen=9000)
        self.selected_log_fields: list[str] = []

        # Deduplication guard: prevents stacking multiple concurrent
        # _tick_async coroutines from rapid _notify() calls.
        self._notify_pending: bool = False

    # ---------------------------------------------------------------
    # Public surface
    # ---------------------------------------------------------------

    @property
    def engine_control(self) -> EngineControl:
        """Direct control surface for the engine (run/stop/reset/...)."""
        return self._engine_control

    @property
    def registry(self) -> ControllerRegistry:
        return self._registry

    @property
    def bridge(self) -> Any:
        """Escape hatch — exposes the bridge for legacy code paths.

        New children should NOT use this; they subscribe and react to
        ``on_tick`` instead.
        """
        return self._bridge

    @property
    def tick_s(self) -> float:
        return self._tick_s

    def snapshot(self) -> Mapping[str, float]:
        """Return a copy of the latest snapshot (lock-safe)."""
        with self._lock:
            return dict(self._snapshot)

    def get(self, modal_key: str, default: float = 0.0) -> float:
        """Single-value snapshot read (LocalStore-compatible)."""
        with self._lock:
            if modal_key in self._snapshot:
                return float(self._snapshot[modal_key])
        return float(default)

    def subscribe(self, child: Subscriber) -> Callable[[], None]:
        """Register a child.

        Returns an unsubscribe callable.
        """
        with self._lock:
            self._subscribers.append(child)

        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._subscribers.remove(child)
                except ValueError:
                    pass

        return _unsubscribe

    def get_history_since(self, watermark: int) -> list[dict]:
        """Return steps added to history since the given watermark
        step_index."""
        with self._lock:
            # History is small enough that a list comprehension over
            # 9000 items is fast,
            # but we can optimize by iterating backward or just filtering.
            return [step for step in self._history if step.get('step_index', -1) > watermark]

    def set_selected_log_fields(self, fields: list[str]) -> None:
        """Update the shared UI presentation state for plotting/logging."""
        with self._lock:
            self.selected_log_fields = list(fields)
        try:
            self._bridge.set_selected_log_fields(list(fields))
        except Exception:
            pass

    def toggle_log_field(self, field: str) -> None:
        """Toggle a field in the shared UI presentation state."""
        with self._lock:
            if field in self.selected_log_fields:
                self.selected_log_fields.remove(field)
            else:
                self.selected_log_fields.append(field)
        try:
            self._bridge.set_selected_log_fields(list(self.selected_log_fields))
        except Exception:
            pass

    # ---------------------------------------------------------------
    # Bidirectional path — child → engine
    # ---------------------------------------------------------------

    def request_write(self, modal_key: str, value: float) -> None:
        """Push a value upstream from a child to the engine.

        Three routes, decided by the registry spec:

        1. **Status key** (``role='status'``): writes the bridge's
           ``controller_mode`` and triggers
           ``apply_runtime_configuration(restart_if_needed=True)``.
           The next step record will echo the new mode and the hub
           fans it out to every child.
        2. **Writable input** (``writable=True`` with an
           ``engine_tag``): calls ``bridge.set_input_value(tag, v)``
           which updates ``bridge.state.input_overrides``. The next
           ``_run_one_step`` will use it as an external input and
           the echo flows back via the normal tick.
        3. **Local / read-only**: just writes the snapshot cache
           (so a child that requests a write to a PV key still
           sees its value until the engine overrides it).

        The snapshot cache is updated immediately in cases (2) and
        (3) so a read on the SAME tick sees the new value (the
        engine echo on the NEXT tick will confirm).
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            return

        spec = self._registry.get_by_modal_key(modal_key)

        import time

        with self._lock:
            self._write_locks[modal_key] = time.time() + 1.5

        # Status key → bridge controller_mode + apply
        if spec is not None and spec.role == 'status':
            mode_name = mode_code_to_name(int(v))
            try:
                self._adapter.set_controller_mode(mode_name)
            except Exception:
                logger.exception('Failed to apply status key %r', modal_key)
            self._notify()
            return

        # Writable input → bridge.set_input_value
        engine_tag = spec.engine_tag if (spec and spec.writable) else None
        if engine_tag:
            try:
                self._adapter.set_input_value(engine_tag, v)
            except Exception:
                logger.exception('Failed to apply engine tag %r', engine_tag)
            self._write_snapshot({modal_key: v})
            with self._lock:
                self._local_dirty_keys.add(modal_key)
            self._notify()
            return

        # Local / read-only — just cache
        self._write_snapshot({modal_key: v})
        with self._lock:
            self._local_dirty_keys.add(modal_key)
        self._notify()

    def _notify(self) -> None:
        """Force an immediate broadcast without waiting for the next tick.

        Debounced: only one pending _tick_async coroutine can be in flight
        at a time, preventing rapid request_write() calls from stacking
        dozens of coroutines that each lock the snapshot.
        """
        with self._lock:
            if not self._subscribers:
                return
            if self._notify_pending:
                return
            self._notify_pending = True
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run_notify())
        except RuntimeError:
            with self._lock:
                self._notify_pending = False

    async def _run_notify(self) -> None:
        """Run a single deduped _tick_async and clear the pending flag."""
        try:
            await self._tick_async()
        finally:
            with self._lock:
                self._notify_pending = False

    # ---------------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------------

    def start(self) -> None:
        """Seed initial snapshot.

        (Timer is now driven by the page clients).
        """
        if getattr(self, '_started', False):
            return
        self._started = True
        # Seed-from-storage: if the bridge's persistent state has
        # no records yet (typical right after a page reload) but
        # we have a stashed last snapshot for this browser, merge
        # it into the in-memory snapshot so the UI doesn't flash
        # zeros while the first engine tick arrives. The bridge's
        # own tick on the next loop will overwrite any key whose
        # authoritative value differs — we just want a "no flash"
        # paint.
        try:
            self._seed_from_storage()
        except Exception:
            logger.debug('SignalHub: _seed_from_storage failed', exc_info=True)

    def _seed_from_storage(self) -> None:
        """Merge a previously-persisted snapshot (if any) into the in-memory
        snapshot. Keys already present in the bridge's authoritative state are
        NOT overwritten — the bridge wins.

        Storage shape: ``app.storage.user['hub_snapshot:<case>']`` is
        a dict of ``{modal_key: float}``. We only read; writes happen
        in :meth:`_maybe_persist_snapshot` below.
        """
        try:
            from nicegui import app
        except Exception:
            return
        case = self._case_slug()
        if not case:
            return
        key = f'hub_snapshot:{case}'
        try:
            stored = app.storage.user.get(key) or {}
        except Exception:
            return
        if not isinstance(stored, dict) or not stored:
            return
        with self._lock:
            for modal_key, value in stored.items():
                if modal_key in self._snapshot:
                    continue
                try:
                    self._snapshot[str(modal_key)] = float(value)
                except (TypeError, ValueError):
                    continue
        self._apply_derived_pairs()

    def _apply_derived_pairs(self) -> None:
        """Mirror derived pairs into the snapshot (e.g. fi102_pv = fi101_pv).

        Called after seeding from storage and after reset so derived
        keys are populated even when no engine step has arrived yet.
        """
        derived = (
            self._derived_pairs
            if hasattr(self, '_derived_pairs')
            else self._registry.derived_pairs()
        )
        if not derived:
            return
        with self._lock:
            for source_key, target_key in derived:
                if source_key in self._snapshot:
                    v = float(self._snapshot[source_key])
                    self._snapshot[target_key] = v

    def _maybe_persist_snapshot(self) -> None:
        """Every Nth tick, mirror the snapshot to ``app.storage.user``.

        Throttled to every 100th tick (~10 s at 10 Hz) so the JSON
        serialization cost is minimal. The write is fire-and-forget via
        ``asyncio.ensure_future`` so we never block the event loop tick.
        """
        if not hasattr(self, '_persist_counter'):
            self._persist_counter = 0
        self._persist_counter += 1
        if self._persist_counter % 100 != 0:
            return
        try:
            from nicegui import app
        except Exception:
            return
        case = self._case_slug()
        if not case:
            return
        key = f'hub_snapshot:{case}'
        with self._lock:
            payload = dict(self._snapshot)

        async def _write_async() -> None:
            try:
                await asyncio.to_thread(lambda: app.storage.user.__setitem__(key, payload))
            except Exception:
                logger.debug(
                    'SignalHub: failed to persist snapshot to storage',
                    exc_info=True,
                )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_write_async())
        except RuntimeError:
            pass

    def _case_slug(self) -> str:
        """Best-effort case name for the storage key.

        Falls back to the bridge's ``case_name`` (which every bridge
        has) and finally to the empty string (which skips persistence).
        """
        try:
            name = str(getattr(self._bridge, 'case_name', '') or '')
            if name:
                return name
        except Exception:
            pass
        return ''

    def stop(self) -> None:
        timer = self._timer
        self._timer = None
        if timer is None:
            return
        try:
            cancel = getattr(timer, 'cancel', None)
            if callable(cancel):
                cancel()
            deactivate = getattr(timer, 'deactivate', None)
            if callable(deactivate):
                deactivate()
        except Exception:
            pass

    async def tick_once(self) -> None:
        """Drive one tick manually (used by tests and post-reset rebuilds)."""
        await self._tick_async()

    # ---------------------------------------------------------------
    # Reset support — clears the snapshot to its initial seed and
    # bumps the reset counter so children can detect the boundary.
    # ---------------------------------------------------------------

    def reset_snapshot_to_seed(self) -> None:
        """Re-seed the snapshot from the registry's initial seed.

        Mirrors the legacy ``BaseBridgeStore._reseed_cache_from_bridge``
        — called by the v2 page's Reset handler AFTER the bridge has
        been reset, so children that snapshot-read during the same tick
        see the post-reset baseline.
        """
        with self._lock:
            self._snapshot = dict(self._initial_seed)
            # Replenish input echoes from bridge.input_overrides (which
            # the bridge re-seeded from its case config).
            try:
                overrides = getattr(self._bridge.state, 'input_overrides', None) or {}
                input_map = self._registry.input_field_to_override()
                # input_map is now engine_tag → modal_key
                for engine_tag, modal_key in input_map.items():
                    if engine_tag in overrides:
                        try:
                            self._snapshot[modal_key] = float(
                                overrides[engine_tag],
                            )
                        except (TypeError, ValueError):
                            pass
            except Exception:
                pass
            self._sim_time = 0.0
            self._step_index = -1
            self._reset_counter += 1
            self._history.clear()
        self._apply_derived_pairs()

    # ---------------------------------------------------------------
    # Internal — tick loop
    # ---------------------------------------------------------------

    async def _tick_async(self) -> None:
        t0 = time.perf_counter()
        drain_cap = self._drain_cap

        # ── 1. Drain via pure Adapter ──
        delta_dict, meta, raw_steps = self._adapter.drain_and_parse(drain_cap)

        # Append to history
        if raw_steps:
            with self._lock:
                self._history.extend(raw_steps)

        # Apply write-locks: ignore values for keys that were recently modified
        now = time.time()
        with self._lock:
            locked_keys = [k for k, exp in self._write_locks.items() if now < exp]
            # Clean up expired locks
            for k in list(self._write_locks.keys()):
                if now >= self._write_locks[k]:
                    del self._write_locks[k]

        for lk in locked_keys:
            if lk in delta_dict:
                del delta_dict[lk]

        if delta_dict:
            self._write_snapshot(delta_dict)

        # Apply derived mirrors
        derived = self._derived_pairs
        if derived and (delta_dict or not self._snapshot):
            for source_key, target_key in derived:
                if source_key in delta_dict:
                    v = float(delta_dict[source_key])
                    with self._lock:
                        if self._snapshot.get(target_key) != v:
                            self._snapshot[target_key] = v
                    delta_dict[target_key] = v

        with self._lock:
            local_dirty = self._local_dirty_keys.copy()
            self._local_dirty_keys.clear()

        delta_keys = frozenset(list(delta_dict.keys()) + list(local_dirty))

        # ── 3. Atomic fan-out ──
        # Take a snapshot of the subscriber list under the lock so a
        # ``subscribe()`` during dispatch can't mutate it mid-iteration.
        # All children are then called sequentially with the SAME
        # ``delta_keys`` frozenset and the SAME snapshot mapping —
        # that's what makes "satu angka di tick yang sama" structural.

        status_changed = meta.status != getattr(self, '_last_meta_status', None)
        mode_changed = meta.mode != getattr(self, '_last_meta_mode', None)
        reset_changed = meta.reset_counter != getattr(self, '_last_reset_counter', None)
        force_dispatch = status_changed or mode_changed or reset_changed

        if delta_keys or force_dispatch:
            self._last_meta_status = meta.status
            self._last_meta_mode = meta.mode
            self._last_reset_counter = meta.reset_counter

            with self._lock:
                subscribers_snapshot = tuple(self._subscribers)
                snapshot_view = dict(self._snapshot)

            for child in subscribers_snapshot:
                try:
                    child.on_tick(delta_keys, snapshot_view, meta)
                except Exception:
                    logger.exception(
                        'SignalHub: subscriber %r raised in on_tick',
                        type(child).__name__,
                    )

            # ── 3b. UI Sync Manager — only when data changed ──
            # Skip the sync pass on idle ticks to reduce CPU load.
            try:
                self._tick_counter += 1
                self.ui_sync.on_tick()
                self.ui_sync.set_running_state(meta.status in ('running', 'starting'))
            except Exception:
                logger.debug('SignalHub: ui_sync.on_tick failed', exc_info=True)

        self._maybe_persist_snapshot()

        # ── Adaptive drain cap update (2A) ──
        elapsed = time.perf_counter() - t0
        if elapsed > self._tick_s:
            self._drain_cap = max(1, drain_cap // 2)
        elif elapsed < self._tick_s * 0.5:
            self._drain_cap = min(40, drain_cap * 2)

        # Yield the event loop so NiceGUI can process WebSocket frames
        # (clicks, hover, open/close dialogs) between ticks.
        await asyncio.sleep(0)

    def _write_snapshot(self, new_values: Mapping[str, float]) -> None:
        with self._lock:
            for key, value in new_values.items():
                self._snapshot[key] = float(value)

    def get_field_color(self, field_name: str, active_fields: list[str]) -> str:
        """Assign a unique and stable color to each selected/active field.

        Guarantees that no two active fields share the same color within
        active_fields.
        """
        if not hasattr(self, '_field_colors'):
            self._field_colors = {}

        # If already assigned, return it.
        if field_name in self._field_colors:
            return self._field_colors[field_name]

        from app.hub.perf_monitor import _DCS_TRACE_PALETTE

        # What colors are currently used by active fields?
        active_set = set(active_fields)
        used_colors = {self._field_colors[f] for f in active_set if f in self._field_colors}

        # Find the first color in the palette that is not used
        for color in _DCS_TRACE_PALETTE:
            if color not in used_colors:
                self._field_colors[field_name] = color
                return color

        # Fallback if we run out of colors (more than 56 active fields)
        try:
            available = list(getattr(self._bridge.state, 'available_log_fields', []) or [])
            idx = available.index(field_name)
        except ValueError:
            idx = 0
        fallback_color = _DCS_TRACE_PALETTE[idx % len(_DCS_TRACE_PALETTE)]
        self._field_colors[field_name] = fallback_color
        return fallback_color

    def update_bridge_selected_fields(self) -> None:
        """Update the bridge's selected_log_fields with the union of all PM and
        DL selections across all sessions."""
        pm_map = getattr(self, 'pm_selected_fields_map', {})
        dl_map = getattr(self, 'dl_selected_fields_map', {})

        union_set = set()
        for fields in pm_map.values():
            union_set.update(fields)
        for fields in dl_map.values():
            union_set.update(fields)

        self._bridge.set_selected_log_fields(list(union_set))


__all__ = [
    'SignalHub',
    'Subscriber',
    'TickMeta',
    'mode_name_to_code',
    'mode_code_to_name',
]
