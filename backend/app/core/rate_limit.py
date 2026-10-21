import threading
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Depends, HTTPException, status
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User


class UserRateLimiter:
    """Sliding-window per-user in-memory rate limiter."""

    def __init__(self, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._user_requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check_rate_limit(self, user_id: str) -> None:
        """Record request and raise 429 if user exceeds rate limit window."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            recent = [ts for ts in self._user_requests[user_id] if ts > cutoff]
            if len(recent) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please wait before making more requests.",
                    headers={"Retry-After": "60"},
                )
            recent.append(now)
            self._user_requests[user_id] = recent

    def clear(self) -> None:
        """Clear rate limit history (useful for test resets)."""
        with self._lock:
            self._user_requests.clear()


rate_limiter = UserRateLimiter(
    limit=settings.RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)


async def rate_limited_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that authenticates user and enforces rate limit."""
    rate_limiter.check_rate_limit(str(current_user.id))
    return current_user
