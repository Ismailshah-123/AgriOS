"""Small in-process sliding-window rate limiter.

Scope: a single API process (the FYP deployment). With several workers or hosts
this must move to a shared store; that limitation is documented in SECURITY notes.
"""

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._events[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        return q

    def retry_after(self, key: str, now: float | None = None) -> int:
        """Seconds until another event is allowed; 0 when allowed now."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._prune(key, now)
            if len(q) < self.max_events:
                return 0
            return max(1, int(self.window - (now - q[0])) + 1)

    def hit(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
