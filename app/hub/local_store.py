# app/hub/local_store.py

"""Tiny in-memory key/value store used by controller modals.

This is the case-agnostic base storage layer that every case's
controller modals can use as a stand-in for an engine. It exposes the
same ``get`` / ``set`` / ``all`` API that
``app.hub.children.modal_child.HubStoreAdapter`` exposes — so a modal
class can be wired to either the engine (via the ``HubStoreAdapter``) or
to a pure-UI ``LocalStore`` without code changes.

Moved here from the legacy ``app/pid/_shared/local_store.py`` during the
v1 purge — same code, new location.
"""

from __future__ import annotations


class LocalStore:
    """Tiny in-memory key/value store used by the modal.

    The modal treats it like the engine: it reads and writes named
    keys. There is no simulation here; the values are just numbers.

    Cases that need engine connectivity wrap the bridge in a
    :class:`HubStoreAdapter` (``app/hub/children/modal_child.py``)
    instead — it implements the same ``get`` / ``set`` / ``all``
    interface.
    """

    def __init__(self, initial: dict[str, float]):
        self._values: dict[str, float] = dict(initial)

    def get(self, key: str, default: float = 0.0) -> float:
        return float(self._values.get(key, default))

    def set(self, key: str, value: float) -> None:
        self._values[key] = float(value)

    def all(self) -> dict[str, float]:
        return dict(self._values)


__all__ = ['LocalStore']
