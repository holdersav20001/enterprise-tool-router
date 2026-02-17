"""Integration tests for Redis caching with real Redis instance.

Week 4 Commit 23: Redis Caching Layer - Integration Tests

These tests require Redis to be running:
    docker-compose up redis

Run integration tests only:
    pytest -m integration

Skip integration tests:
    pytest -m "not integration"

These tests validate:
1. Real Redis connectivity and persistence
2. Cache operations work with actual Redis backend
3. TTL expiration works correctly
4. Concurrent access patterns
5. Error handling with real network conditions
"""
import pytest
import time
from enterprise_tool_router.cache import CacheManager
from enterprise_tool_router.sql_planner import SqlPlanner
from enterprise_tool_router.llm.providers import MockProvider


@pytest.mark.integration
class TestRedisConnectivity:
    """Test basic Redis connectivity and operations."""

    def test_redis_connection_successful(self, redis_cache):
        """Test that we can connect to Redis successfully."""
        assert redis_cache.is_enabled is True
        assert redis_cache._redis is not None

    def test_redis_ping_works(self, redis_client):
        """Test that Redis responds to ping."""
        assert redis_client.ping() is True

    def test_cache_set_and_get(self, redis_cache):
        """Test basic set and get operations with real Redis."""
        # Set a value
        success = redis_cache.set("test query", {"sql": "SELECT 1", "confidence": 0.9})
        assert success is True

        # Get the value back
        cached = redis_cache.get("test query")
        assert cached is not None
        assert cached["sql"] == "SELECT 1"
        assert cached["confidence"] == 0.9

    def test_cache_miss_returns_none(self, redis_cache):
        """Test that cache miss returns None."""
        result = redis_cache.get("nonexistent query")
        assert result is None

    def test_cache_delete_works(self, redis_cache):
        """Test that delete removes entries."""
        # Set a value
        redis_cache.set("test", {"data": "value"})
        assert redis_cache.get("test") is not None

        # Delete it
        redis_cache.delete("test")
        assert redis_cache.get("test") is None

    def test_cache_clear_flushes_all(self, redis_cache):
        """Test that clear removes all entries."""
        # Set multiple values
        redis_cache.set("query1", {"sql": "SELECT 1"})
        redis_cache.set("query2", {"sql": "SELECT 2"})

        # Verify they exist
        assert redis_cache.get("query1") is not None
        assert redis_cache.get("query2") is not None

        # Clear cache
        redis_cache.clear()

        # Verify all gone
        assert redis_cache.get("query1") is None
        assert redis_cache.get("query2") is None


@pytest.mark.integration
class TestRedisTTL:
    """Test TTL (time-to-live) expiration."""

    def test_ttl_expiration(self, redis_url):
        """Test that cache entries expire after TTL."""
        # Create cache with 2 second TTL
        cache = CacheManager(ttl_seconds=2, redis_url=redis_url)

        if not cache.is_enabled:
            pytest.skip("Redis not available")

        # Set a value
        cache.set("test", {"data": "expires soon"})

        # Immediately should exist
        assert cache.get("test") is not None

        # Wait for TTL to expire (2 seconds + buffer)
        time.sleep(2.5)

        # Should be gone
        assert cache.get("test") is None

    def test_different_ttls(self, redis_url):
        """Test that different TTLs can be set."""
        # Short TTL cache
        short_cache = CacheManager(ttl_seconds=1, redis_url=redis_url)
        # Long TTL cache
        long_cache = CacheManager(ttl_seconds=10, redis_url=redis_url)

        if not short_cache.is_enabled or not long_cache.is_enabled:
            pytest.skip("Redis not available")

        # Set values with different TTLs
        short_cache.set("short", {"data": "1 second"})
        long_cache.set("long", {"data": "10 seconds"})

        # Both exist initially
        assert short_cache.get("short") is not None
        assert long_cache.get("long") is not None

        # Wait 1.5 seconds
        time.sleep(1.5)

        # Short should be gone, long should remain
        assert short_cache.get("short") is None
        assert long_cache.get("long") is not None


@pytest.mark.integration
class TestRedisStats:
    """Test cache statistics tracking with real Redis."""

    def test_stats_track_hits_and_misses(self, redis_cache):
        """Test that hits and misses are tracked correctly."""
        # Initial stats
        stats = redis_cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0

        # Cache miss
        redis_cache.get("nonexistent")
        stats = redis_cache.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0

        # Set and hit
        redis_cache.set("query", {"sql": "SELECT 1"})
        redis_cache.get("query")
        stats = redis_cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1

        # Another hit
        redis_cache.get("query")
        stats = redis_cache.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1

    def test_stats_hit_rate_calculation(self, redis_cache):
        """Test that hit rate is calculated correctly."""
        # 3 hits, 2 misses = 60% hit rate
        redis_cache.set("q1", {"sql": "SELECT 1"})
        redis_cache.set("q2", {"sql": "SELECT 2"})

        redis_cache.get("q1")  # hit
        redis_cache.get("q2")  # hit
        redis_cache.get("q1")  # hit
        redis_cache.get("q3")  # miss
        redis_cache.get("q4")  # miss

        stats = redis_cache.get_stats()
        assert stats.hits == 3
        assert stats.misses == 2
        assert stats.hit_rate == pytest.approx(0.6, abs=0.01)


@pytest.mark.integration
class TestRedisIntegrationWithPlanner:
    """Test SqlPlanner integration with real Redis cache."""

    def test_planner_with_real_redis_avoids_llm_call(self, redis_cache):
        """
        Integration test: Verify cache actually prevents LLM calls with real Redis.

        Acceptance Criteria:
        - First query calls LLM and caches result
        - Second identical query hits cache, no LLM call
        - Results are identical
        """
        provider = MockProvider(
            response_data={
                "sql": "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100",
                "confidence": 0.95,
                "explanation": "Revenue by region"
            }
        )

        # Track LLM calls
        llm_call_count = 0
        original_generate = provider.generate_structured

        def counted_generate(*args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            return original_generate(*args, **kwargs)

        provider.generate_structured = counted_generate

        # Create planner with real Redis cache
        planner = SqlPlanner(provider, cache_manager=redis_cache)

        # First query - LLM called, result cached in Redis
        result1 = planner.plan("show revenue by region")
        assert llm_call_count == 1
        assert result1.sql is not None

        # Second query - cache hit in Redis, NO LLM call
        result2 = planner.plan("show revenue by region")
        assert llm_call_count == 1  # Still 1! Cache hit!
        assert result2.sql == result1.sql

        # Verify cache stats show the hit
        stats = redis_cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_cache_persists_across_planner_instances(self, redis_cache):
        """Test that cache persists even when creating new planner instances."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        # First planner instance
        planner1 = SqlPlanner(provider, cache_manager=redis_cache)
        result1 = planner1.plan("test query")

        # Create NEW planner instance with SAME cache
        planner2 = SqlPlanner(provider, cache_manager=redis_cache)
        result2 = planner2.plan("test query")

        # Should get cached result
        assert result1.sql == result2.sql
        stats = redis_cache.get_stats()
        assert stats.hits == 1  # Second query hit cache

    def test_cache_only_stores_successful_responses(self, redis_cache):
        """Test that errors are NOT cached in Redis."""
        # Provider that fails
        failing_provider = MockProvider(should_fail=True)
        planner = SqlPlanner(failing_provider, cache_manager=redis_cache)

        # Query that fails
        result = planner.plan("test query")
        assert "error" in str(type(result).__name__).lower()

        # Verify nothing was cached
        stats = redis_cache.get_stats()
        assert stats.sets == 0  # No cache writes for errors


@pytest.mark.integration
class TestRedisConcurrency:
    """Test concurrent access patterns with Redis."""

    def test_multiple_cache_managers_share_data(self, redis_url):
        """Test that multiple CacheManager instances share the same Redis data."""
        cache1 = CacheManager(ttl_seconds=60, redis_url=redis_url)
        cache2 = CacheManager(ttl_seconds=60, redis_url=redis_url)

        if not cache1.is_enabled or not cache2.is_enabled:
            pytest.skip("Redis not available")

        # Write with cache1
        cache1.set("shared query", {"sql": "SELECT 1", "confidence": 0.9})

        # Read with cache2
        result = cache2.get("shared query")
        assert result is not None
        assert result["sql"] == "SELECT 1"

    def test_cache_key_collision_handled(self, redis_cache):
        """Test that different queries don't collide."""
        # Set two similar but different queries
        redis_cache.set("show revenue", {"sql": "SELECT revenue FROM sales"})
        redis_cache.set("show sales", {"sql": "SELECT sales FROM orders"})

        # Both should be retrievable independently
        revenue_result = redis_cache.get("show revenue")
        sales_result = redis_cache.get("show sales")

        assert revenue_result["sql"] == "SELECT revenue FROM sales"
        assert sales_result["sql"] == "SELECT sales FROM orders"


@pytest.mark.integration
class TestRedisErrorHandling:
    """Test error handling with real Redis."""

    def test_cache_handles_malformed_data_gracefully(self, redis_client, redis_cache):
        """Test that corrupted Redis data doesn't crash the app."""
        # Manually insert malformed data into Redis
        cache_key = redis_cache._generate_key("test query")
        redis_client.set(cache_key, "this is not valid JSON")

        # Should return None instead of crashing
        result = redis_cache.get("test query")
        assert result is None

        # Error should be tracked
        stats = redis_cache.get_stats()
        assert stats.errors > 0

    def test_cache_disabled_when_redis_unavailable(self):
        """Test graceful fallback when Redis is not available."""
        # Try to connect to non-existent Redis
        cache = CacheManager(
            ttl_seconds=60,
            redis_url="redis://localhost:9999/0",  # Wrong port
            enabled=True
        )

        # Cache should be disabled
        assert cache.is_enabled is False

        # Operations should not crash
        result = cache.get("test")
        assert result is None

        success = cache.set("test", {"data": "value"})
        assert success is False


@pytest.mark.integration
@pytest.mark.slow
class TestRedisPerformance:
    """Test cache performance benefits with real Redis."""

    def test_cache_reduces_response_time(self, redis_cache):
        """Test that cached responses are faster than LLM calls."""
        import time

        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        # Add artificial delay to simulate LLM latency
        original_generate = provider.generate_structured
        def slow_generate(*args, **kwargs):
            time.sleep(0.1)  # 100ms delay
            return original_generate(*args, **kwargs)

        provider.generate_structured = slow_generate

        planner = SqlPlanner(provider, cache_manager=redis_cache)

        # First call - slow (LLM + cache write)
        start = time.time()
        planner.plan("test query")
        first_call_duration = time.time() - start

        # Second call - fast (cache hit)
        start = time.time()
        planner.plan("test query")
        second_call_duration = time.time() - start

        # Cache hit should be significantly faster
        assert second_call_duration < first_call_duration
        assert second_call_duration < 0.05  # Less than 50ms (much faster than 100ms LLM call)
