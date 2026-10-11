"""Per-process daily ceiling on external calls. In memory: it resets at 00:00 UTC and on every server restart."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Callable, Optional


class CallBudget:
    """Counts external HTTP attempts (retries included, because each one can cost quota)."""

    def __init__(self, daily_limit: int, clock: Optional[Callable[[], datetime]] = None) -> None:
        if daily_limit < 1:
            raise ValueError("daily_limit must be >= 1")
        self.daily_limit = daily_limit
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._day = None
        self._used = 0

    def _roll(self) -> None:
        today = self._clock().date()
        if today != self._day:
            self._day, self._used = today, 0

    def acquire(self) -> bool:
        with self._lock:
            self._roll()
            if self._used >= self.daily_limit:
                return False
            self._used += 1
            return True

    def used(self) -> int:
        with self._lock:
            self._roll()
            return self._used

    def remaining(self) -> int:
        return max(0, self.daily_limit - self.used())
