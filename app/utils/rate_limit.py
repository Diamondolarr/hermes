from math import ceil

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi_limiter.depends import RateLimiter

from app.core.config import settings
from app.services.admin_monitoring import PROVIDER_INTERNAL, record_api_usage_event


async def _noop_rate_limit() -> None:
    return None


async def rate_limit_identifier(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "anonymous"


async def rate_limit_callback(request: Request, _: Response, pexpire: int) -> None:
    retry_after = max(1, ceil(pexpire / 1000))
    identifier = await rate_limit_identifier(request)
    record_api_usage_event(
        workspace_id=None,
        provider=PROVIDER_INTERNAL,
        feature="rate_limit",
        success=False,
        metadata={
            "path": request.url.path,
            "method": request.method,
            "ip_address": identifier,
            "retry_after_seconds": retry_after,
        },
    )
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Rate limit exceeded. Retry in {retry_after} seconds.",
        headers={"Retry-After": str(retry_after)},
    )


def rate_limit(times: int, seconds: int):
    if not settings.rate_limiting_enabled:
        return Depends(_noop_rate_limit)
    return Depends(RateLimiter(times=times, seconds=seconds))
