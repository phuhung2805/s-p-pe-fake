"""
In-memory, thread-safe sliding-window rate limiter (Module 1 - Auth & Security).

Used to throttle brute-force login attempts and password-reset requests per
client IP. This keeps the prototype dependency-free; in a distributed
deployment swap the backing store for Redis while keeping the same interface.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Dict, Deque, Optional, Tuple


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, max_events: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Records an event for ``key`` and returns ``(allowed, retry_after)``.

        ``allowed`` is False when the number of events in the trailing
        ``window_seconds`` window already reached ``max_events``. ``retry_after``
        is the number of seconds until the oldest event leaves the window.
        """
        now = time.time()
        with self._lock:
            bucket = self._events[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_events:
                retry_after = int(bucket[0] + window_seconds - now) + 1
                return False, max(1, retry_after)

            bucket.append(now)
            return True, 0

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)


# Shared limiters
login_ip_limiter = SlidingWindowRateLimiter()
password_reset_ip_limiter = SlidingWindowRateLimiter()


def reset_all() -> None:
    """Test / maintenance helper: clears every limiter."""
    login_ip_limiter.reset()
    password_reset_ip_limiter.reset()
