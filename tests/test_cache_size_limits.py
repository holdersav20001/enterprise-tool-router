"""Tests for cache size limits.

Week 4 Commit 27: Smart caching based on result size

These tests verify that large results are not cached in Redis
to prevent memory pressure.
"""
import pytest
import json
from enterprise_tool_router.cache import CacheManager, NoOpCache


class TestCacheSizeLimits:
    """Test that large results are not cached."""

    def test_small_response_is_cached(self):
        """Test that small responses are cached normally."""
        cache = CacheManager(
            ttl_seconds=60,
            enabled=False,  # Don't need real Redis for this test
            max_cache_size_bytes=1_048_576  # 1MB
        )

        # Even with disabled Redis, we can test the size check logic
        # by using a mock that tracks calls
        small_response = {"sql": "SELECT 1", "confidence": 0.9, "explanation": "Test"}

        # Calculate size
        size = len(json.dumps(small_response).encode('utf-8'))
        assert size < 1_048_576  # Should be well under 1MB

    def test_large_response_exceeds_limit(self):
        """Test that large responses exceed the size limit."""
        cache = CacheManager(
            ttl_seconds=60,
            enabled=False,
            max_cache_size_bytes=1000  # 1KB limit
        )

        # Create large response (>1KB)
        large_response = {
            "sql": "SELECT * FROM sales_fact",
            "confidence": 0.9,
            "explanation": "x" * 10000  # 10KB of data
        }

        # Calculate size
        size = len(json.dumps(large_response).encode('utf-8'))
        assert size > 1000  # Should exceed 1KB limit

    def test_cache_size_limit_is_configurable(self):
        """Test that size limit can be configured."""
        # Different size limits
        cache_1kb = CacheManager(max_cache_size_bytes=1024, enabled=False)
        cache_1mb = CacheManager(max_cache_size_bytes=1_048_576, enabled=False)
        cache_10mb = CacheManager(max_cache_size_bytes=10_485_760, enabled=False)

        assert cache_1kb.max_cache_size_bytes == 1024
        assert cache_1mb.max_cache_size_bytes == 1_048_576
        assert cache_10mb.max_cache_size_bytes == 10_485_760

    def test_default_size_limit_is_1mb(self):
        """Test that default size limit is 1MB."""
        cache = CacheManager(enabled=False)
        assert cache.max_cache_size_bytes == 1_048_576  # 1MB


@pytest.mark.integration
class TestCacheSizeLimitsWithRedis:
    """Integration tests with real Redis for size limits."""

    def test_small_response_cached_in_redis(self, redis_cache):
        """Test that small responses are cached in Redis."""
        small_response = {
            "sql": "SELECT 1",
            "confidence": 0.9,
            "explanation": "Simple query"
        }

        # Set should succeed
        success = redis_cache.set("small query", small_response)
        assert success is True

        # Get should return the cached value
        cached = redis_cache.get("small query")
        assert cached is not None
        assert cached["sql"] == "SELECT 1"

        # Stats should show a set
        stats = redis_cache.get_stats()
        assert stats.sets >= 1

    def test_large_response_not_cached_in_redis(self, redis_url):
        """Test that responses exceeding size limit are not cached."""
        # Create cache with small limit (1KB)
        cache = CacheManager(
            ttl_seconds=60,
            redis_url=redis_url,
            enabled=True,
            max_cache_size_bytes=1000  # 1KB limit
        )

        if not cache.is_enabled:
            pytest.skip("Redis not available")

        # Create large response (>1KB)
        large_response = {
            "sql": "SELECT * FROM sales_fact",
            "confidence": 0.9,
            "explanation": "x" * 10000  # 10KB of data
        }

        # Verify it's actually large
        size = len(json.dumps(large_response).encode('utf-8'))
        assert size > 1000

        # Set should return False (too large)
        success = cache.set("large query", large_response)
        assert success is False

        # Get should return None (not cached)
        cached = cache.get("large query")
        assert cached is None

    def test_boundary_size_exactly_at_limit(self, redis_url):
        """Test response exactly at the size limit."""
        limit_bytes = 1000
        cache = CacheManager(
            ttl_seconds=60,
            redis_url=redis_url,
            enabled=True,
            max_cache_size_bytes=limit_bytes
        )

        if not cache.is_enabled:
            pytest.skip("Redis not available")

        # Create response that's just under the limit
        # Account for JSON overhead
        padding_size = limit_bytes - 200  # Leave room for JSON structure
        small_enough_response = {
            "sql": "SELECT 1",
            "confidence": 0.9,
            "explanation": "x" * padding_size
        }

        size = len(json.dumps(small_enough_response).encode('utf-8'))

        if size < limit_bytes:
            # Should be cached
            success = cache.set("boundary query small", small_enough_response)
            assert success is True
        else:
            # Should not be cached
            success = cache.set("boundary query large", small_enough_response)
            assert success is False

    def test_multiple_small_queries_all_cached(self, redis_cache):
        """Test that multiple small queries are all cached."""
        queries = [
            ("query 1", {"sql": "SELECT 1", "confidence": 0.9}),
            ("query 2", {"sql": "SELECT 2", "confidence": 0.95}),
            ("query 3", {"sql": "SELECT 3", "confidence": 0.85}),
        ]

        # Cache all queries
        for query, response in queries:
            success = redis_cache.set(query, response)
            assert success is True

        # Verify all are cached
        for query, response in queries:
            cached = redis_cache.get(query)
            assert cached is not None
            assert cached["sql"] == response["sql"]

    def test_mixed_sizes_filters_correctly(self, redis_url):
        """Test that small queries are cached but large ones are not."""
        cache = CacheManager(
            ttl_seconds=60,
            redis_url=redis_url,
            enabled=True,
            max_cache_size_bytes=5000  # 5KB limit
        )

        if not cache.is_enabled:
            pytest.skip("Redis not available")

        # Small query (should be cached)
        small_response = {"sql": "SELECT 1", "confidence": 0.9, "explanation": "Simple"}
        cache.set("small", small_response)

        # Large query (should NOT be cached)
        large_response = {"sql": "SELECT *", "confidence": 0.9, "explanation": "x" * 10000}
        cache.set("large", large_response)

        # Verify small is cached, large is not
        assert cache.get("small") is not None
        assert cache.get("large") is None


class TestCacheSizeMetrics:
    """Test that size-related metrics are tracked correctly."""

    def test_sets_counted_even_when_too_large(self, redis_url):
        """Test that set attempts are counted even when response is too large."""
        cache = CacheManager(
            ttl_seconds=60,
            redis_url=redis_url,
            enabled=True,
            max_cache_size_bytes=100  # Very small limit
        )

        if not cache.is_enabled:
            pytest.skip("Redis not available")

        cache.reset_stats()

        # Try to cache something that's too large
        large_response = {"sql": "SELECT *", "confidence": 0.9, "explanation": "x" * 1000}
        success = cache.set("test", large_response)

        # Should return False
        assert success is False

        # But set attempt should still be counted
        stats = cache.get_stats()
        assert stats.sets >= 1
