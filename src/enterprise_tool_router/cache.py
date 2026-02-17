"""Cache manager for LLM-generated SQL responses.

Week 4 Commit 23: Redis Caching Layer

Implements caching for validated SQL responses to reduce repeated LLM calls.
Only caches successful, safe SQL responses - failures are never cached.

Key Design:
- Cache key: SHA256 hash of (query + tool)
- Only successful SqlPlanSchema responses are cached
- SqlPlanErrorSchema responses are NOT cached (failures should be retried)
- Configurable TTL (time-to-live)
- Redis backend with graceful fallback (no-op cache if Redis unavailable)

Example:
    >>> from enterprise_tool_router.cache import CacheManager
    >>> cache = CacheManager(ttl_seconds=300)  # 5 minutes
    >>>
    >>> # Cache hit avoids LLM call
    >>> result = cache.get("show me revenue")
    >>> if result is None:
    ...     result = call_llm("show me revenue")
    ...     cache.set("show me revenue", result)
"""
import hashlib
import json
from typing import Optional, Any
from dataclasses import dataclass

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisError = Exception  # type: ignore


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int
    misses: int
    sets: int
    errors: int

    @property
    def total_requests(self) -> int:
        """Total cache requests (hits + misses)."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0-1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def to_dict(self) -> dict:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate
        }


class CacheManager:
    """Manage caching of LLM-generated SQL responses.

    Week 4 Commit 23: Reduces repeated LLM calls for identical queries.

    Only caches successful SqlPlanSchema responses. Errors are never cached
    to allow retries. Uses Redis when available, falls back to no-op cache.

    Attributes:
        ttl_seconds: Time-to-live for cache entries in seconds
        enabled: Whether caching is enabled (auto-detects Redis availability)

    Example:
        >>> cache = CacheManager(ttl_seconds=300)  # 5 minute TTL
        >>>
        >>> # Try cache first
        >>> cached = cache.get("show revenue by region")
        >>> if cached:
        ...     print("Cache hit! No LLM call needed")
        ... else:
        ...     result = llm.generate_sql("show revenue by region")
        ...     cache.set("show revenue by region", result)
    """

    def __init__(
        self,
        ttl_seconds: int = 1800,
        redis_url: Optional[str] = None,
        enabled: bool = True,
        max_cache_size_bytes: int = 1_048_576
    ):
        """Initialize cache manager.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 1800 = 30 minutes)
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
            enabled: Whether to enable caching (default: True)
            max_cache_size_bytes: Max size to cache in bytes (default: 1MB). Skip caching if larger.
        """
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled and REDIS_AVAILABLE
        self._max_size = max_cache_size_bytes

        # Stats tracking
        self._stats = CacheStats(hits=0, misses=0, sets=0, errors=0)

        # Redis connection
        self._redis: Optional[Any] = None
        if self._enabled:
            try:
                redis_url = redis_url or "redis://127.0.0.1:6379/0"  # Use 127.0.0.1 for Windows/Docker compatibility
                self._redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,  # 5 second timeout for network latency
                    socket_timeout=5
                )
                # Test connection
                self._redis.ping()
            except Exception:
                # Redis not available - disable caching gracefully
                self._enabled = False
                self._redis = None

    def get(self, query: str) -> Optional[dict]:
        """Get cached response for a query.

        Args:
            query: The natural language query

        Returns:
            Cached response dict if found, None if cache miss or error
        """
        if not self._enabled or not self._redis:
            self._stats.misses += 1
            return None

        try:
            cache_key = self._generate_key(query)
            cached_value = self._redis.get(cache_key)

            if cached_value:
                self._stats.hits += 1
                # Deserialize JSON
                return json.loads(cached_value)
            else:
                self._stats.misses += 1
                return None

        except Exception:
            self._stats.errors += 1
            return None  # Graceful degradation on error

    def set(self, query: str, response: dict, bypass: bool = False) -> bool:
        """Cache a successful response with size checking.

        Args:
            query: The natural language query
            response: The response dict to cache (must be SqlPlanSchema, not error)
            bypass: If True, skip caching even if enabled (Week 4 Commit 27)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self._enabled or not self._redis or bypass:
            return False

        try:
            # Week 4 Commit 27: Check size before caching
            value = json.dumps(response)
            size_bytes = len(value.encode('utf-8'))

            if size_bytes > self._max_size:
                # Too large - skip Redis caching
                self._stats.sets += 1  # Count as attempt
                return False

            cache_key = self._generate_key(query)
            # Set with TTL
            self._redis.setex(cache_key, self._ttl_seconds, value)
            self._stats.sets += 1
            return True

        except Exception:
            self._stats.errors += 1
            return False

    def delete(self, query: str) -> bool:
        """Delete a cached entry.

        Args:
            query: The natural language query

        Returns:
            True if deleted, False otherwise
        """
        if not self._enabled or not self._redis:
            return False

        try:
            cache_key = self._generate_key(query)
            self._redis.delete(cache_key)
            return True
        except Exception:
            return False

    def clear(self) -> bool:
        """Clear all cache entries.

        WARNING: This flushes the entire Redis database.
        Only use in testing or if Redis is dedicated to this app.

        Returns:
            True if cleared, False otherwise
        """
        if not self._enabled or not self._redis:
            return False

        try:
            self._redis.flushdb()
            return True
        except Exception:
            return False

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with hits, misses, sets, errors, and hit rate
        """
        return self._stats

    def reset_stats(self) -> None:
        """Reset cache statistics to zero."""
        self._stats = CacheStats(hits=0, misses=0, sets=0, errors=0)

    @property
    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled

    @property
    def ttl_seconds(self) -> int:
        """Get TTL in seconds."""
        return self._ttl_seconds

    @property
    def max_cache_size_bytes(self) -> int:
        """Get maximum cacheable size in bytes."""
        return self._max_size

    def _generate_key(self, query: str) -> str:
        """Generate cache key from query.

        Uses SHA256 hash to create consistent, short keys.
        Prefixed with 'sql:' to namespace cache entries.

        Args:
            query: The natural language query

        Returns:
            Cache key string (e.g., 'sql:abc123...')
        """
        # Normalize query (lowercase, strip whitespace)
        normalized = query.lower().strip()

        # Hash for consistent key
        hash_obj = hashlib.sha256(normalized.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()

        # Prefix with namespace
        return f"sql:{hash_hex}"


class NoOpCache(CacheManager):
    """No-op cache implementation for testing.

    Always returns cache miss (None) and does nothing on set.
    Useful for testing cache-disabled scenarios.
    """

    def __init__(self):
        """Initialize no-op cache."""
        # Don't call super().__init__() to avoid Redis connection
        self._enabled = False
        self._ttl_seconds = 0
        self._redis = None
        self._stats = CacheStats(hits=0, misses=0, sets=0, errors=0)

    def get(self, query: str) -> None:
        """Always return cache miss."""
        self._stats.misses += 1
        return None

    def set(self, query: str, response: dict) -> bool:
        """Do nothing."""
        return False
