"""Rate limiter for preventing abuse.

Week 4 Commit 24: Rate Limiting
Week 4 Commit 25: Structured error taxonomy integration

Implements per-IP or per-user rate limiting using a sliding window algorithm.
Prevents excessive requests and protects the system from abuse.

Design:
- Sliding window algorithm (counts requests in last N seconds)
- Configurable limits (e.g., 10 requests per minute)
- Per-IP or per-user tracking
- Redis backend with in-memory fallback
- Graceful error responses when limit exceeded

Example:
    >>> from enterprise_tool_router.rate_limiter import RateLimiter
    >>> limiter = RateLimiter(max_requests=10, window_seconds=60)
    >>>
    >>> # Check if request is allowed
    >>> if limiter.is_allowed("user123"):
    ...     process_request()
    ... else:
    ...     return "Rate limit exceeded"
"""
import time
from typing import Optional, Dict
from dataclasses import dataclass
from collections import deque, defaultdict
from threading import Lock

# Week 4 Commit 25: Import structured error taxonomy
from .errors import RateLimitError as StructuredRateLimitError

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisError = Exception  # type: ignore


class RateLimitError(StructuredRateLimitError):
    """Raised when rate limit is exceeded.

    Week 4 Commit 24: Rate limiting protection.
    Week 4 Commit 25: Now inherits from StructuredRateLimitError.
    """

    def __init__(self, identifier: str, limit: int, window: int, retry_after: float):
        """Initialize rate limit error.

        Args:
            identifier: The user/IP that hit the limit
            limit: Maximum requests allowed
            window: Time window in seconds
            retry_after: Seconds until retry is allowed
        """
        message = (
            f"Rate limit exceeded for {identifier}: "
            f"{limit} requests per {window}s. "
            f"Retry after {retry_after:.1f}s"
        )
        details = {
            "identifier": identifier,
            "limit": limit,
            "window_seconds": window,
            "retry_after_seconds": retry_after
        }
        super().__init__(
            message=message,
            retryable=True,
            details=details
        )
        # Keep attributes for backward compatibility
        self.identifier = identifier
        self.limit = limit
        self.window = window
        self.retry_after = retry_after


@dataclass
class RateLimitStats:
    """Rate limit statistics for monitoring."""
    total_requests: int
    allowed_requests: int
    rejected_requests: int
    unique_identifiers: int

    @property
    def rejection_rate(self) -> float:
        """Rate of rejected requests (0.0-1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.rejected_requests / self.total_requests

    def to_dict(self) -> dict:
        """Convert stats to dictionary."""
        return {
            "total_requests": self.total_requests,
            "allowed_requests": self.allowed_requests,
            "rejected_requests": self.rejected_requests,
            "unique_identifiers": self.unique_identifiers,
            "rejection_rate": self.rejection_rate
        }


class RateLimiter:
    """Rate limiter with sliding window algorithm.

    Week 4 Commit 24: Prevents abuse through request rate limiting.

    Tracks requests per identifier (IP/user) and rejects requests
    that exceed the configured limit within the time window.

    Attributes:
        max_requests: Maximum requests allowed per window
        window_seconds: Time window in seconds
        enabled: Whether rate limiting is enabled

    Example:
        >>> limiter = RateLimiter(max_requests=10, window_seconds=60)
        >>>
        >>> # Check before processing
        >>> if not limiter.is_allowed("192.168.1.1"):
        ...     raise RateLimitError("Too many requests")
        >>>
        >>> # Record request
        >>> limiter.record_request("192.168.1.1")
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        redis_url: Optional[str] = None,
        enabled: bool = True
    ):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window (default: 100)
            window_seconds: Time window in seconds (default: 60)
            redis_url: Redis connection URL (default: use in-memory)
            enabled: Whether to enable rate limiting (default: True)
        """
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._enabled = enabled

        # Stats
        self._stats = RateLimitStats(
            total_requests=0,
            allowed_requests=0,
            rejected_requests=0,
            unique_identifiers=0
        )

        # In-memory storage (fallback if Redis unavailable)
        self._request_times: Dict[str, deque] = defaultdict(lambda: deque())
        self._lock = Lock()

        # Redis connection (optional)
        self._redis: Optional[any] = None
        self._use_redis = False

        if REDIS_AVAILABLE and redis_url:
            try:
                self._redis = redis.from_url(
                    redis_url,
                    decode_responses=False,  # We'll handle bytes
                    socket_connect_timeout=1,
                    socket_timeout=1
                )
                # Test connection
                self._redis.ping()
                self._use_redis = True
            except Exception:
                # Fall back to in-memory
                self._use_redis = False
                self._redis = None

    def is_allowed(self, identifier: str) -> bool:
        """Check if request from identifier is allowed.

        Does NOT record the request - call record_request() separately.

        Args:
            identifier: User ID, IP address, or other identifier

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        if not self._enabled:
            return True

        current_count = self._get_request_count(identifier)
        return current_count < self._max_requests

    def record_request(self, identifier: str) -> bool:
        """Record a request from identifier.

        Args:
            identifier: User ID, IP address, or other identifier

        Returns:
            True if request was allowed and recorded, False if rejected

        Raises:
            RateLimitError: If rate limit exceeded (when check_limit=True)
        """
        if not self._enabled:
            self._stats.total_requests += 1
            self._stats.allowed_requests += 1
            return True

        self._stats.total_requests += 1

        # Check if allowed
        if not self.is_allowed(identifier):
            self._stats.rejected_requests += 1
            return False

        # Record request
        current_time = time.time()

        if self._use_redis and self._redis:
            try:
                # Use Redis sorted set with scores as timestamps
                key = f"ratelimit:{identifier}"
                # Add current request
                self._redis.zadd(key, {str(current_time): current_time})
                # Remove old requests outside window
                cutoff = current_time - self._window_seconds
                self._redis.zremrangebyscore(key, 0, cutoff)
                # Set expiry on key
                self._redis.expire(key, self._window_seconds)
            except Exception:
                # Fall back to in-memory
                self._record_in_memory(identifier, current_time)
        else:
            self._record_in_memory(identifier, current_time)

        self._stats.allowed_requests += 1
        return True

    def check_limit(self, identifier: str) -> None:
        """Check rate limit and raise exception if exceeded.

        Args:
            identifier: User ID, IP address, or other identifier

        Raises:
            RateLimitError: If rate limit exceeded
        """
        if not self.is_allowed(identifier):
            retry_after = self._get_retry_after(identifier)
            raise RateLimitError(
                identifier=identifier,
                limit=self._max_requests,
                window=self._window_seconds,
                retry_after=retry_after
            )

    def get_stats(self) -> RateLimitStats:
        """Get rate limiting statistics.

        Returns:
            RateLimitStats with request counts and rejection rate
        """
        # Update unique identifier count
        if self._use_redis and self._redis:
            try:
                # Count keys matching ratelimit:*
                keys = self._redis.keys("ratelimit:*")
                self._stats.unique_identifiers = len(keys)
            except Exception:
                pass
        else:
            with self._lock:
                self._stats.unique_identifiers = len(self._request_times)

        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics to zero."""
        self._stats = RateLimitStats(
            total_requests=0,
            allowed_requests=0,
            rejected_requests=0,
            unique_identifiers=0
        )

    def clear(self, identifier: Optional[str] = None) -> None:
        """Clear rate limit data.

        Args:
            identifier: If provided, clear only this identifier.
                       If None, clear all data.
        """
        if identifier:
            if self._use_redis and self._redis:
                try:
                    self._redis.delete(f"ratelimit:{identifier}")
                except Exception:
                    pass
            with self._lock:
                if identifier in self._request_times:
                    del self._request_times[identifier]
        else:
            # Clear all
            if self._use_redis and self._redis:
                try:
                    keys = self._redis.keys("ratelimit:*")
                    if keys:
                        self._redis.delete(*keys)
                except Exception:
                    pass
            with self._lock:
                self._request_times.clear()

    @property
    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled."""
        return self._enabled

    @property
    def max_requests(self) -> int:
        """Get maximum requests per window."""
        return self._max_requests

    @property
    def window_seconds(self) -> int:
        """Get time window in seconds."""
        return self._window_seconds

    # Private methods

    def _get_request_count(self, identifier: str) -> int:
        """Get current request count for identifier.

        Args:
            identifier: User ID or IP address

        Returns:
            Number of requests in current window
        """
        current_time = time.time()
        cutoff = current_time - self._window_seconds

        if self._use_redis and self._redis:
            try:
                key = f"ratelimit:{identifier}"
                # Count requests after cutoff
                count = self._redis.zcount(key, cutoff, current_time)
                return count
            except Exception:
                # Fall back to in-memory
                pass

        # In-memory count
        with self._lock:
            if identifier not in self._request_times:
                return 0

            # Remove old requests
            request_times = self._request_times[identifier]
            while request_times and request_times[0] < cutoff:
                request_times.popleft()

            return len(request_times)

    def _record_in_memory(self, identifier: str, timestamp: float) -> None:
        """Record request in memory.

        Args:
            identifier: User ID or IP address
            timestamp: Request timestamp
        """
        with self._lock:
            self._request_times[identifier].append(timestamp)

            # Clean up old entries
            cutoff = timestamp - self._window_seconds
            while (self._request_times[identifier] and
                   self._request_times[identifier][0] < cutoff):
                self._request_times[identifier].popleft()

    def _get_retry_after(self, identifier: str) -> float:
        """Get seconds until retry is allowed.

        Args:
            identifier: User ID or IP address

        Returns:
            Seconds until retry allowed (0 if allowed now)
        """
        current_time = time.time()
        cutoff = current_time - self._window_seconds

        if self._use_redis and self._redis:
            try:
                key = f"ratelimit:{identifier}"
                # Get oldest request timestamp
                oldest = self._redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    # Time until oldest request expires
                    return max(0, (oldest_time + self._window_seconds) - current_time)
            except Exception:
                pass

        # In-memory fallback
        with self._lock:
            if identifier not in self._request_times:
                return 0.0

            request_times = self._request_times[identifier]
            if not request_times:
                return 0.0

            # Time until oldest request expires from window
            oldest = request_times[0]
            retry_after = max(0, (oldest + self._window_seconds) - current_time)
            return retry_after
