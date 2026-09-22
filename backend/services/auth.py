"""API auth (optional API key) and simple in-memory rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request

from config import get_settings


def _client_id(request: Request, api_key: str | None) -> str:
    if api_key:
        return f"key:{api_key[:12]}"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    if request.client:
        return f"ip:{request.client.host}"
    return "ip:unknown"


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock_ts = time.monotonic()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({limit} requests per {window_seconds}s)",
            )
        bucket.append(now)


rate_limiter = RateLimiter()


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str | None:
    """
    When ENABLE_AUTH / APP_API_KEY is set, require X-API-Key or Bearer token.
    Health checks bypass this dependency (mounted without it).
    """
    settings = get_settings()
    provided = x_api_key
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()

    if settings.enable_auth:
        if not settings.api_key:
            raise HTTPException(
                status_code=500,
                detail="Auth enabled but APP_API_KEY is not configured",
            )
        if provided != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    client = _client_id(request, provided)
    if settings.rate_limit_per_minute > 0:
        rate_limiter.check(client, settings.rate_limit_per_minute)
    return provided


def optional_auth_dependency() -> Callable:
    return require_api_key
