"""
In-memory rate limiting — suitable for single-process Railway deployment.
No external dependencies required.

For multi-instance deployments, replace SlidingWindowLimiter with
an Upstash Redis / Valkey backend.
"""
import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Thread-safe sliding window counter backed by asyncio.Lock."""

    def __init__(self) -> None:
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._ops = 0

    async def is_allowed(self, key: str, limit: int, window_sec: int) -> bool:
        """Returns True and records the hit if within limit, False otherwise."""
        async with self._lock:
            now = time.monotonic()
            dq = self._windows[key]
            cutoff = now - window_sec
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            # Periodic GC: drop empty buckets to avoid unbounded dict growth
            self._ops += 1
            if self._ops >= 50_000:
                self._ops = 0
                dead = [k for k, v in self._windows.items() if not v]
                for k in dead:
                    del self._windows[k]
            return True


# ── Singletons ─────────────────────────────────────────────────────────────
ip_limiter   = SlidingWindowLimiter()   # keyed by IP  — auth probing, registration
user_limiter = SlidingWindowLimiter()   # keyed by tg_id — general API throttle


# ── AI daily limits by subscription tier ───────────────────────────────────
# Actual usage counters live in Supabase (ai_usage table) — see db/queries.py.

_AI_LIMITS: dict[str, int] = {
    "free": 5,
    "pro":  50,
    "vip":  9_999,  # effectively unlimited
}


def ai_daily_limit(status: str | None) -> int:
    return _AI_LIMITS.get(status or "free", _AI_LIMITS["free"])
