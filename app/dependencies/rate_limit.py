from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.middleware.rate_limit import (
    RateLimitOptions,
    build_rate_limit_key,
    rate_limiter,
)


def rate_limit(limit: int, window_ms: int) -> Callable[[Request], None]:
    options = RateLimitOptions(limit=limit, window_ms=window_ms)

    def dependency(request: Request) -> None:
        key = build_rate_limit_key(
            request.method,
            request.url.path,
            request.headers.get("authorization"),
        )

        if not rate_limiter.check(key, options):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again shortly.",
                    }
                },
            )

    return dependency
