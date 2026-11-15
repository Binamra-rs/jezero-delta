"""Small in-process sliding-window rate limiter.

Per-process: with N Uvicorn workers the effective limit is N× the setting.
For a stricter global limit add a Cloudflare rate-limiting rule (documented
in docs/07-deployment.md) or swap this class for a Redis-backed one.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.per_minute <= 0:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= self.per_minute:
                retry = int(60 - (now - q[0])) + 1
                raise HTTPException(429, "Too many requests, please slow down", headers={"Retry-After": str(retry)})
            q.append(now)
            if len(self._hits) > 50_000:  # bound memory
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                    self._hits.pop(k, None)


def client_ip(request: Request) -> str:
    # Behind Cloudflare the real client address is in CF-Connecting-IP.
    return (request.headers.get("cf-connecting-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "unknown"))
