"""Shared model residency: at most `max_resident` heavy models loaded at once, never unloading one that is in use.

Rules enforced by this class (and nothing else is claimed):
- A model is loaded only inside `use()`, serialized per model (one thread loads, others wait).
- Making room unloads only models with no active user and an `unload` callable; if none qualifies the caller waits
  and gives up after `acquire_timeout` seconds with `MODEL_BUSY` (retryable). No indefinite waits.
- `use()` is NOT re-entrant: do not request a second model while holding one (the services never do).
- The count is of models this manager knows about. Memory actually returned to the OS is up to Python/ONNX Runtime.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional

from core.contracts import VistaError

log = logging.getLogger("vista.models")
_SLICE = 0.25  # seconds; waiters re-check cancel/shutdown at least this often


class _Entry:
    __slots__ = ("name", "load", "unload", "is_loaded", "active", "loading")

    def __init__(self, name: str, load: Callable[[], None], is_loaded: Callable[[], bool],
                 unload: Optional[Callable[[], None]]) -> None:
        self.name, self.load, self.is_loaded, self.unload = name, load, is_loaded, unload
        self.active = 0  # users currently inside use(), including a loader in progress
        self.loading = False


class ModelManager:
    def __init__(self, max_resident: int = 1, acquire_timeout: float = 30.0) -> None:
        if max_resident < 1:
            raise ValueError("max_resident must be >= 1")
        if acquire_timeout <= 0:
            raise ValueError("acquire_timeout must be > 0")
        self.max_resident = max_resident
        self.acquire_timeout = acquire_timeout
        self._cond = threading.Condition()
        self._entries: Dict[str, _Entry] = {}
        self._closed = False

    def register(self, name: str, load: Callable[[], None], is_loaded: Callable[[], bool],
                 unload: Optional[Callable[[], None]] = None) -> None:
        with self._cond:
            if name in self._entries:
                raise ValueError(f"model '{name}' is already registered")
            self._entries[name] = _Entry(name, load, is_loaded, unload)

    def close(self) -> None:
        """Refuse new acquisitions and wake all waiters. Loaded models are left to their owners."""
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def status(self) -> Dict[str, Dict[str, Any]]:
        with self._cond:
            return {e.name: {"loaded": bool(e.is_loaded()), "loading": e.loading, "active": e.active,
                             "evictable": e.unload is not None} for e in self._entries.values()}

    # -- internals (call with the condition held) --
    def _check(self, cancel: Optional[threading.Event]) -> None:
        if self._closed:
            raise VistaError("unavailable", "SERVER_SHUTTING_DOWN", "The server is shutting down.", retryable=True)
        if cancel is not None and cancel.is_set():
            raise VistaError("cancelled", "CANCELLED", "The task was cancelled.")

    def _wait(self, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise VistaError("resource_limit", "MODEL_BUSY",
                             "Another model is in use and memory limits prevent loading this one. Try again shortly.",
                             retryable=True, details={"waited_seconds": self.acquire_timeout})
        self._cond.wait(min(remaining, _SLICE))

    def _evict(self, victim: _Entry) -> None:
        try:
            assert victim.unload is not None
            victim.unload()
        except Exception as exc:  # message may contain paths; log the type only
            log.error("unload of '%s' failed: %s", victim.name, type(exc).__name__)
            raise VistaError("provider_internal", "MODEL_UNLOAD_FAILED",
                             "Another model could not be unloaded to make room.", retryable=True) from None
        if victim.is_loaded():
            raise VistaError("provider_internal", "MODEL_UNLOAD_FAILED",
                             "Another model could not be unloaded to make room.", retryable=True)
        log.info("unloaded model '%s' to make room", victim.name)

    def _acquire(self, name: str, cancel: Optional[threading.Event]) -> _Entry:
        deadline = time.monotonic() + self.acquire_timeout
        with self._cond:
            entry = self._entries.get(name)
            if entry is None:
                raise VistaError("provider_internal", "MODEL_UNKNOWN", "Unexpected server error.")
            while True:
                self._check(cancel)
                if entry.loading:
                    self._wait(deadline)
                    continue
                if entry.is_loaded():
                    entry.active += 1
                    return entry
                others = [e for e in self._entries.values()
                          if e is not entry and (e.loading or e.is_loaded())]
                excess = len(others) - (self.max_resident - 1)
                if excess > 0:
                    victims = [e for e in others if not e.loading and e.active == 0 and e.unload is not None]
                    if len(victims) < excess:
                        self._wait(deadline)
                        continue
                    for victim in victims[:excess]:
                        self._evict(victim)
                entry.loading = True
                entry.active += 1  # reserved: nobody can evict this entry while it loads or is used
                break
        try:
            entry.load()  # outside the lock: loading can take seconds and must not block release() calls
        except BaseException:
            with self._cond:
                entry.loading = False
                entry.active -= 1
                self._cond.notify_all()
            raise
        with self._cond:
            entry.loading = False
            self._cond.notify_all()
        return entry

    def _release(self, entry: _Entry) -> None:
        with self._cond:
            entry.active -= 1
            self._cond.notify_all()

    @contextmanager
    def use(self, name: str, cancel: Optional[threading.Event] = None) -> Iterator[None]:
        """Hold model `name` loaded and un-evictable for the duration of the `with` block."""
        entry = self._acquire(name, cancel)
        try:
            yield
        finally:
            self._release(entry)
