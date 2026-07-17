"""Rate limiting via Redis sliding window."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a tool."""

    per_minute: int = 60
    per_hour: int = 1000
    per_day: int = 10_000
    cost_per_day_usd: float = 0.0


DEFAULT_LIMITS = {
    "default": RateLimitConfig(per_minute=60, per_hour=1000, per_day=10_000),
    "pbi_query_dax": RateLimitConfig(per_minute=30, per_hour=500, per_day=5_000),
    "pbi_apply_approved_change": RateLimitConfig(per_minute=5, per_hour=20, per_day=50),
    "ai_generation": RateLimitConfig(
        per_minute=10, per_hour=100, per_day=1_000, cost_per_day_usd=10.0
    ),
}


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit: str, current: int, max_allowed: int):
        self.limit = limit
        self.current = current
        self.max_allowed = max_allowed
        super().__init__(f"Rate limit exceeded: {max_allowed}/{limit} (current: {current})")


class CostLimitError(Exception):
    """Raised when daily cost limit is exceeded."""

    def __init__(self, current_usd: float, max_usd: float):
        self.current_usd = current_usd
        self.max_usd = max_usd
        super().__init__(f"Cost limit exceeded: ${current_usd:.2f} > ${max_usd:.2f}")


class RateLimiter:
    """Redis-based sliding window rate limiter."""

    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.limits = DEFAULT_LIMITS

    async def close(self):
        await self.redis.close()

    def _window_seconds(self, window: str) -> int:
        return {"1m": 60, "1h": 3600, "1d": 86_400}.get(window, 60)

    async def check(
        self,
        user_id: str,
        tool: str,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        """Check rate limits. Raises if any limit is exceeded."""
        config = self.limits.get(tool, self.limits["default"])

        # Check request count limits
        for window, max_count in [
            ("1m", config.per_minute),
            ("1h", config.per_hour),
            ("1d", config.per_day),
        ]:
            key = f"rate:{user_id}:{tool}:{window}"
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, self._window_seconds(window))
            if current > max_count:
                logger.warning(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    tool=tool,
                    window=window,
                    current=current,
                    max=max_count,
                )
                raise RateLimitError(window, int(current), max_count)

        # Check cost limits
        if config.cost_per_day_usd > 0 and estimated_cost_usd > 0:
            cost_key = f"cost:{user_id}:{tool}:1d"
            current_cost = await self.redis.incrbyfloat(cost_key, estimated_cost_usd)
            if current_cost > config.cost_per_day_usd:
                logger.error(
                    "cost_limit_exceeded",
                    user_id=user_id,
                    tool=tool,
                    current_usd=current_cost,
                    max_usd=config.cost_per_day_usd,
                )
                raise CostLimitError(current_cost, config.cost_per_day_usd)

    async def pause_user(self, user_id: str, duration_seconds: int = 3600) -> None:
        """Temporarily pause a user (used on cost limit breach)."""
        key = f"paused:{user_id}"
        await self.redis.setex(key, duration_seconds, "1")
        logger.warning("user_paused", user_id=user_id, duration=duration_seconds)

    async def is_paused(self, user_id: str) -> bool:
        """Check if a user is currently paused."""
        return bool(await self.redis.exists(f"paused:{user_id}"))