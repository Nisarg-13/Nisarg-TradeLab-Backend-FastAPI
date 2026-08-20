from dataclasses import dataclass
from time import time


@dataclass
class RateLimitOptions:
    limit: int
    window_ms: int


@dataclass
class RateLimitBucket:
    count: int
    reset_at: float


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, RateLimitBucket] = {}

    def check(self, key: str, options: RateLimitOptions) -> bool:
        now = time() * 1000
        bucket = self._buckets.get(key)

        if bucket is None or bucket.reset_at <= now:
            self._buckets[key] = RateLimitBucket(count=1, reset_at=now + options.window_ms)
            return True

        if bucket.count >= options.limit:
            return False

        bucket.count += 1
        return True


rate_limiter = InMemoryRateLimiter()


def build_rate_limit_key(method: str, path: str, authorization: str | None) -> str:
    auth_header = authorization or "anonymous"
    route = f"{method}:{path}"
    return f"{route}:{auth_header}"
