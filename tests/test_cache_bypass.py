"""Tests for cache bypass functionality.

Week 4 Commit 27: Cache bypass parameter

These tests verify that bypass_cache=True forces fresh LLM generation
and skips both Redis cache and query_history lookup.
"""
import pytest
from enterprise_tool_router.router import ToolRouter
from enterprise_tool_router.sql_planner import SqlPlanner
from enterprise_tool_router.llm.providers import MockProvider
from enterprise_tool_router.cache import CacheManager


class TestCacheBypassPlanner:
    """Test bypass_cache parameter in SqlPlanner."""

    def test_bypass_cache_skips_redis(self):
        """Test that bypass_cache=True skips Redis cache lookup."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
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

        # Create planner with cache
        cache = CacheManager(enabled=False)  # Use NoOp cache for unit test
        planner = SqlPlanner(provider, cache_manager=cache)

        # First call - LLM called
        result1 = planner.plan("show sales")
        assert llm_call_count == 1

        # Second call without bypass - would hit cache if Redis was enabled
        # But with NoOp cache, it calls LLM again
        result2 = planner.plan("show sales", bypass_cache=False)
        assert llm_call_count == 2  # NoOp cache doesn't cache

        # Third call WITH bypass - forces LLM call regardless
        result3 = planner.plan("show sales", bypass_cache=True)
        assert llm_call_count == 3

    def test_bypass_false_allows_caching(self):
        """Test that bypass_cache=False allows normal caching."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT region FROM sales_fact LIMIT 10",
                "confidence": 0.95,
                "explanation": "Test"
            }
        )

        llm_call_count = 0
        original_generate = provider.generate_structured

        def counted_generate(*args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            return original_generate(*args, **kwargs)

        provider.generate_structured = counted_generate

        # Note: This test uses NoOp cache so it won't actually cache
        # Integration test with Redis will verify actual caching
        cache = CacheManager(enabled=False)
        planner = SqlPlanner(provider, cache_manager=cache)

        # Multiple calls without bypass
        planner.plan("test query", bypass_cache=False)
        planner.plan("test query", bypass_cache=False)

        # With NoOp cache, both calls hit LLM
        assert llm_call_count == 2


@pytest.mark.integration
class TestCacheBypassWithRedis:
    """Integration tests for bypass with real Redis."""

    def test_bypass_forces_llm_call_despite_cache(self, redis_cache):
        """Test that bypass_cache=True forces fresh LLM generation even when cached."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
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

        # First call (populates cache)
        result1 = planner.plan("show sales data")
        assert llm_call_count == 1
        assert result1.sql is not None

        # Second call without bypass (cache hit)
        result2 = planner.plan("show sales data", bypass_cache=False)
        assert llm_call_count == 1  # Still 1! (cache hit)
        assert result2.sql == result1.sql

        # Third call WITH bypass (forces LLM)
        result3 = planner.plan("show sales data", bypass_cache=True)
        assert llm_call_count == 2  # Now 2! (cache bypassed)
        assert result3.sql is not None

        # Fourth call without bypass (cache hit again)
        result4 = planner.plan("show sales data", bypass_cache=False)
        assert llm_call_count == 2  # Still 2 (cache hit)

    def test_bypass_does_not_cache_result(self, redis_cache):
        """Test that bypass_cache=True also prevents caching the result."""
        from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema

        provider = MockProvider(
            response_data={
                "sql": "SELECT 1 LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        planner = SqlPlanner(provider, cache_manager=redis_cache)

        # Call with bypass
        result = planner.plan("bypassed query", bypass_cache=True)
        assert isinstance(result, SqlPlanSchema)
        assert result.sql is not None

        # Verify it was NOT cached
        cached = redis_cache.get("bypassed query")
        assert cached is None  # Should not be in cache

    def test_normal_call_after_bypass_caches(self, redis_cache):
        """Test that normal call after bypass properly caches."""
        from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema

        provider = MockProvider(
            response_data={
                "sql": "SELECT 2 LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        planner = SqlPlanner(provider, cache_manager=redis_cache)

        # First call with bypass (not cached)
        result1 = planner.plan("test query abc", bypass_cache=True)
        assert isinstance(result1, SqlPlanSchema)
        assert redis_cache.get("test query abc") is None

        # Second call without bypass (should cache)
        result2 = planner.plan("test query abc", bypass_cache=False)
        assert isinstance(result2, SqlPlanSchema)
        cached = redis_cache.get("test query abc")
        assert cached is not None
        assert cached["sql"] == result2.sql


class TestCacheBypassEndToEnd:
    """End-to-end tests for bypass through the full stack."""

    def test_bypass_parameter_propagates_through_stack(self):
        """Test that bypass_cache parameter propagates from API to planner."""
        from enterprise_tool_router.tools.sql import SqlTool

        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        llm_call_count = 0
        original_generate = provider.generate_structured

        def counted_generate(*args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            return original_generate(*args, **kwargs)

        provider.generate_structured = counted_generate

        # Create tool with LLM provider (SqlTool doesn't accept cache_manager)
        tool = SqlTool(llm_provider=provider)

        # First call
        tool.run("show me sales", bypass_cache=False)
        assert llm_call_count == 1

        # Second call with bypass
        tool.run("show me sales", bypass_cache=True)
        assert llm_call_count == 2  # Should call LLM again

    def test_router_passes_bypass_to_tool(self):
        """Test that router passes bypass_cache to tool."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT 3 LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        llm_call_count = 0
        original_generate = provider.generate_structured

        def counted_generate(*args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            return original_generate(*args, **kwargs)

        provider.generate_structured = counted_generate

        # Create router with LLM
        router = ToolRouter(llm_provider=provider)

        # First call
        router.handle("show revenue", bypass_cache=False)
        assert llm_call_count == 1

        # Second call with bypass
        router.handle("show revenue", bypass_cache=True)
        assert llm_call_count == 2


class TestBypassWithQueryHistory:
    """Test that bypass also skips query_history lookup."""

    @pytest.mark.integration
    def test_bypass_skips_query_history(self, redis_cache):
        """Test that bypass_cache=True also skips query_history table lookup."""
        from enterprise_tool_router.query_storage import store_query
        from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema

        provider = MockProvider(
            response_data={
                "sql": "SELECT 4 LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        llm_call_count = 0
        original_generate = provider.generate_structured

        def counted_generate(*args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            return original_generate(*args, **kwargs)

        provider.generate_structured = counted_generate

        planner = SqlPlanner(provider, cache_manager=redis_cache)

        # Manually store a query in history (simulating previous execution)
        # Use timestamp to ensure unique query text (avoid conflicts with previous test runs)
        import time
        query_text = f"historical query test {time.time()}"
        store_query(
            natural_language_query=query_text,
            generated_sql="SELECT 999 FROM old_table LIMIT 10",
            confidence=0.95,
            result_size_bytes=100,
            row_count=1,
            execution_time_ms=50,
            retention_days=30
        )

        # Call planner WITHOUT bypass - should find it in history (no LLM call)
        result1 = planner.plan(query_text, bypass_cache=False)
        assert isinstance(result1, SqlPlanSchema)
        assert llm_call_count == 0  # No LLM call (found in history)
        assert "old_table" in result1.sql  # Got the historical SQL

        # Call planner WITH bypass - should skip history and call LLM
        result2 = planner.plan(query_text, bypass_cache=True)
        assert isinstance(result2, SqlPlanSchema)
        assert llm_call_count == 1  # LLM was called (bypassed history)
        assert result2.sql == "SELECT 4 LIMIT 10"  # Got fresh SQL from mock provider


class TestBypassEdgeCases:
    """Test edge cases for bypass functionality."""

    def test_bypass_with_error_still_returns_error(self):
        """Test that bypass with LLM error still returns error."""
        failing_provider = MockProvider(should_fail=True)

        cache = CacheManager(enabled=False)
        planner = SqlPlanner(failing_provider, cache_manager=cache)

        # Should still get error even with bypass
        result = planner.plan("test", bypass_cache=True)
        assert "error" in str(type(result).__name__).lower()

    def test_bypass_default_is_false(self):
        """Test that default bypass_cache value is False."""
        from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema

        provider = MockProvider(
            response_data={"sql": "SELECT 5 LIMIT 10", "confidence": 0.9, "explanation": "Test"}
        )

        cache = CacheManager(enabled=False)
        planner = SqlPlanner(provider, cache_manager=cache)

        # Call without specifying bypass (should default to False)
        result = planner.plan("test query")
        assert isinstance(result, SqlPlanSchema)
        assert result.sql is not None
