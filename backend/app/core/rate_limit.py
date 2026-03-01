"""
Phase 12 Part 4: In-memory rate limiter with Retry-After header support.

Provides per-user request throttling for heavy endpoints (analysis, export, login).
Thread-safe via a lock. Not distributed — suitable for single-process or
vertical-scale deployments. For multi-instance, replace with Redis-backed limiter.
"""
import time
import threading
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request


class RateLimiter:
    """
    Token-bucket rate limiter keyed by user_id.

    Parameters:
        max_requests: Maximum requests allowed in the window.
        window_seconds: Sliding window duration.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """
        Check if the key is within rate limits.
        Raises HTTPException 429 if exceeded.
        """
        now = time.monotonic()
        with self._lock:
            timestamps = self._buckets[key]
            # Prune expired entries
            cutoff = now - self.window_seconds
            self._buckets[key] = [t for t in timestamps if t > cutoff]
            timestamps = self._buckets[key]

            if len(timestamps) >= self.max_requests:
                retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limited",
                        "message": f"Too many requests. Limit: {self.max_requests} per {self.window_seconds}s.",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)

    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limit state. If key is None, reset all."""
        with self._lock:
            if key:
                self._buckets.pop(key, None)
            else:
                self._buckets.clear()


# Pre-configured limiters for different endpoint classes
analysis_limiter = RateLimiter(max_requests=5, window_seconds=60)
export_limiter = RateLimiter(max_requests=10, window_seconds=60)
login_limiter = RateLimiter(max_requests=10, window_seconds=300)  # 10 per 5 min

# Phase 23: Production hardening — additional limiters
contact_limiter = RateLimiter(max_requests=5, window_seconds=300)  # 5 per 5 min per IP
auth_limiter = RateLimiter(max_requests=20, window_seconds=300)    # 20 per 5 min per IP


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For behind proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
