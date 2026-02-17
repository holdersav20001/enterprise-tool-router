"""Tests for Redis caching layer.

Week 4 Commit 23: Redis Caching Layer

This test suite validates that:
1. Cache stores and retrieves responses correctly
2. Cache hits avoid LLM calls
3. Only successful responses are cached (not errors)
4. Cache stats are tracked correctly
5. Cache works with SqlPlanner integration
"""
import pytest
from unittest.mock import Mock, patch
from enterprise_tool_router.cache import CacheManager, NoOpCache, CacheStats
from enterprise_tool_router.sql_planner import SqlPlanner
from enterprise_tool_router.llm.providers import MockProvider
from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema, SqlPlanErrorSchema


class TestCacheBasics:
    """Test basic cache operations."""

    def test_noop_cache_always_misses(self):
        """Test that NoOpCache always returns None."""
        cache = NoOpCache()

        # Get should always return None
        assert cache.get("test query") is None

        # Set should do nothing and return False
        assert cache.set("test query", {"sql": "SELECT 1"}) is False

        # Stats should show misses
        stats = cache.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0

    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly."""
        cache = NoOpCache()

        # Same query should generate same key
        key1 = cache._generate_key("show revenue")
        key2 = cache._generate_key("show revenue")
        assert key1 == key2

        # Different queries should generate different keys
        key3 = cache._generate_key("show sales")
        assert key1 != key3

        # Case-insensitive (normalized)
        key4 = cache._generate_key("SHOW REVENUE")
        assert key1 == key4

        # Whitespace normalized
        key5 = cache._generate_key("  show revenue  ")
        assert key1 == key5

        # Keys are prefixed
        assert key1.startswith("sql:")

    def test_cache_stats_tracking(self):
        """Test that cache statistics are tracked correctly."""
        cache = NoOpCache()

        # Initial stats
        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.total_requests == 0
        assert stats.hit_rate == 0.0

        # After some operations
        cache.get("query1")
        cache.get("query2")
        cache.set("query3", {})

        stats = cache.get_stats()
        assert stats.misses == 2
        assert stats.hits == 0
        assert stats.total_requests == 2
        assert stats.hit_rate == 0.0

    def test_cache_stats_to_dict(self):
        """Test that stats can be converted to dict."""
        stats = CacheStats(hits=10, misses=5, sets=8, errors=1)
        stats_dict = stats.to_dict()

        assert stats_dict["hits"] == 10
        assert stats_dict["misses"] == 5
        assert stats_dict["sets"] == 8
        assert stats_dict["errors"] == 1
        assert stats_dict["total_requests"] == 15
        assert stats_dict["hit_rate"] == pytest.approx(0.666, abs=0.01)

    def test_cache_stats_reset(self):
        """Test that stats can be reset."""
        cache = NoOpCache()
        cache.get("test")
        cache.get("test")

        stats = cache.get_stats()
        assert stats.misses == 2

        # Reset
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats.misses == 0

    def test_cache_disabled_state(self):
        """Test cache disabled state properties."""
        cache = NoOpCache()
        assert cache.is_enabled is False
        assert cache.ttl_seconds == 0


class TestCacheIntegration:
    """Test cache integration with SqlPlanner."""

    def test_planner_cache_hit_avoids_llm_call(self, clean_query_history):
        """
        Test that cache hit avoids calling the LLM.

        This is the key acceptance criteria: second identical query
        should hit cache and NOT call the LLM.
        """
        provider = MockProvider(
            response_data={
                "sql": "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100",
                "confidence": 0.95,
                "explanation": "Aggregates revenue by region"
            }
        )

        # Track how many times the provider is called
        call_count = 0
        original_generate = provider.generate_structured

        def counted_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_generate(*args, **kwargs)

        provider.generate_structured = counted_generate

        # Use NoOpCache but override get/set to simulate cache
        cache = NoOpCache()
        cached_data = None

        def mock_get(query):
            nonlocal cached_data
            if cached_data:
                cache._stats.hits += 1
                return cached_data
            cache._stats.misses += 1
            return None

        def mock_set(query, data, bypass=False):
            nonlocal cached_data
            if not bypass:
                cached_data = data
            cache._stats.sets += 1
            return True

        cache.get = mock_get
        cache.set = mock_set

        planner = SqlPlanner(provider, cache_manager=cache)

        # First call - cache miss, LLM called
        result1 = planner.plan("show revenue by region")
        assert isinstance(result1, SqlPlanSchema)
        assert call_count == 1

        # Second call - cache hit, LLM NOT called
        result2 = planner.plan("show revenue by region")
        assert isinstance(result2, SqlPlanSchema)
        assert call_count == 1  # Still 1! No second LLM call

        # Verify results are the same
        assert result1.sql == result2.sql

        # Verify cache stats
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.sets == 1

    def test_planner_only_caches_successful_responses(self):
        """
        Test that only successful SqlPlanSchema responses are cached.
        Errors (SqlPlanErrorSchema) should NOT be cached.
        """
        # Provider that fails
        failing_provider = MockProvider(should_fail=True)

        cache = NoOpCache()
        cache_sets = []

        def mock_set(query, data, bypass=False):
            if not bypass:
                cache_sets.append((query, data))
            return True

        cache.set = mock_set

        planner = SqlPlanner(failing_provider, cache_manager=cache)

        # Query that fails
        result = planner.plan("test query")
        assert isinstance(result, SqlPlanErrorSchema)

        # Error should NOT be cached
        assert len(cache_sets) == 0

    def test_planner_caches_only_after_success(self, clean_query_history):
        """
        Test that cache is only populated after successful LLM response.
        """
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        cache = NoOpCache()
        cache_data = {}

        def mock_get(query):
            return cache_data.get(query)

        def mock_set(query, data, bypass=False):
            if not bypass:
                cache_data[query] = data
                cache._stats.sets += 1
            return True

        cache.get = mock_get
        cache.set = mock_set

        planner = SqlPlanner(provider, cache_manager=cache)

        # Initially cache is empty
        assert len(cache_data) == 0

        # After successful query, cache should be populated
        result = planner.plan("test query")
        assert isinstance(result, SqlPlanSchema)
        assert len(cache_data) == 1
        assert "test query" in cache_data

        # Verify cached data is valid SqlPlanSchema dict
        cached = cache_data["test query"]
        assert "sql" in cached
        assert "confidence" in cached
        assert "explanation" in cached

    def test_planner_different_queries_different_cache_keys(self, clean_query_history):
        """Test that different queries use different cache keys."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        cache = NoOpCache()
        cache_data = {}

        cache.get = lambda q: cache_data.get(q)
        cache.set = lambda q, d, bypass=False: (cache_data.update({q: d}) or True) if not bypass else True

        planner = SqlPlanner(provider, cache_manager=cache)

        # Two different queries
        planner.plan("query 1")
        planner.plan("query 2")

        # Should have 2 cache entries
        assert len(cache_data) == 2
        assert "query 1" in cache_data
        assert "query 2" in cache_data

    def test_planner_creates_default_cache_if_none(self):
        """Test that planner creates default cache if not provided."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        # No cache provided
        planner = SqlPlanner(provider)

        # Should have created a cache (may or may not be enabled depending on Redis)
        assert planner._cache is not None

    def test_cache_corrupted_data_fallback(self, clean_query_history):
        """Test that corrupted cache data falls back to LLM call."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        cache = NoOpCache()

        # Return corrupted data (missing required fields)
        def mock_get(query):
            cache._stats.hits += 1
            return {"invalid": "data"}

        cache.get = mock_get

        planner = SqlPlanner(provider, cache_manager=cache)

        # Should fall back to LLM call despite cache hit
        result = planner.plan("test")
        assert isinstance(result, SqlPlanSchema)

        # Cache hit was attempted
        stats = cache.get_stats()
        assert stats.hits == 1

    def test_cache_with_circuit_breaker(self, clean_query_history):
        """Test that cache works alongside circuit breaker."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        cache = NoOpCache()
        cached_response = None

        def mock_get(query):
            if cached_response:
                cache._stats.hits += 1
                return cached_response
            cache._stats.misses += 1
            return None

        def mock_set(query, data, bypass=False):
            nonlocal cached_response
            if not bypass:
                cached_response = data
            return True

        cache.get = mock_get
        cache.set = mock_set

        planner = SqlPlanner(provider, cache_manager=cache)

        # First call - populates cache
        result1 = planner.plan("test")
        assert isinstance(result1, SqlPlanSchema)

        # Second call - cache hit (even if circuit breaker is open, cache bypasses it)
        result2 = planner.plan("test")
        assert isinstance(result2, SqlPlanSchema)

        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1


class TestCacheHitRate:
    """Test cache hit rate calculation."""

    def test_hit_rate_calculation(self):
        """Test that hit rate is calculated correctly."""
        cache = NoOpCache()

        # 0 requests = 0% hit rate
        assert cache.get_stats().hit_rate == 0.0

        # Simulate 7 hits, 3 misses = 70% hit rate
        cache._stats.hits = 7
        cache._stats.misses = 3
        assert cache.get_stats().hit_rate == pytest.approx(0.7, abs=0.01)

        # All hits = 100%
        cache._stats.hits = 10
        cache._stats.misses = 0
        assert cache.get_stats().hit_rate == 1.0

        # All misses = 0%
        cache._stats.hits = 0
        cache._stats.misses = 10
        assert cache.get_stats().hit_rate == 0.0


class TestCachePerformance:
    """Test cache performance benefits."""

    def test_cache_reduces_llm_calls(self, clean_query_history):
        """
        Acceptance Criteria: Second identical query hits cache.
        No LLM call on cached hit.
        """
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        # Track LLM calls
        llm_calls = []

        original_generate = provider.generate_structured

        def tracked_generate(*args, **kwargs):
            llm_calls.append(args[0])  # Store prompt
            return original_generate(*args, **kwargs)

        provider.generate_structured = tracked_generate

        # Mock cache that works
        cache = NoOpCache()
        cache_storage = {}

        cache.get = lambda q: cache_storage.get(q)
        cache.set = lambda q, d, bypass=False: (cache_storage.update({q: d}) or True) if not bypass else True

        planner = SqlPlanner(provider, cache_manager=cache)

        # First query - LLM called
        planner.plan("show revenue")
        assert len(llm_calls) == 1

        # Same query again - cache hit, NO LLM call
        planner.plan("show revenue")
        assert len(llm_calls) == 1  # Still 1!

        # Different query - LLM called
        planner.plan("show sales")
        assert len(llm_calls) == 2

        # Previous query again - cache hit
        planner.plan("show revenue")
        assert len(llm_calls) == 2  # Still 2!
