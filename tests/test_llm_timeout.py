"""Tests for LLM timeout protection.

Week 4 Commit 21: LLM Timeout + Cancellation

This test suite validates that:
1. LLM calls can timeout gracefully
2. System does not hang on slow/unresponsive LLMs
3. Timeout errors are properly classified
4. SqlPlanner handles timeouts with safe fallback
"""
import pytest
from enterprise_tool_router.llm.base import LLMTimeoutError
from enterprise_tool_router.llm.providers import MockProvider
from enterprise_tool_router.sql_planner import SqlPlanner
from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema, SqlPlanErrorSchema


class TestLLMTimeout:
    """Test timeout protection for LLM calls."""

    def test_mock_provider_raises_timeout_error(self):
        """Test that MockProvider can simulate timeout."""
        # Arrange: Create provider configured to timeout
        provider = MockProvider(should_timeout=True)

        # Act & Assert: Should raise LLMTimeoutError
        with pytest.raises(LLMTimeoutError) as exc_info:
            provider.generate_structured(
                "test prompt",
                SqlPlanSchema,
                timeout=5.0
            )

        # Verify error message includes timeout value
        assert "5.0s" in str(exc_info.value)
        assert "timeout" in str(exc_info.value).lower()

    def test_mock_provider_timeout_with_custom_timeout(self):
        """Test that timeout error reflects custom timeout value."""
        # Arrange
        provider = MockProvider(should_timeout=True)

        # Act & Assert: Different timeout values
        with pytest.raises(LLMTimeoutError) as exc_info:
            provider.generate_structured(
                "test prompt",
                SqlPlanSchema,
                timeout=15.0
            )

        assert "15.0s" in str(exc_info.value)

    def test_sql_planner_handles_timeout_gracefully(self, clean_query_history):
        """Test that SqlPlanner returns safe error on timeout."""
        # Arrange: Create planner with timeout-prone provider
        provider = MockProvider(should_timeout=True)
        planner = SqlPlanner(provider)

        # Act: Plan should not raise exception, should return error schema
        result = planner.plan("Show me revenue by region", timeout=10.0, bypass_cache=True)

        # Assert: Returns SqlPlanErrorSchema, not exception
        assert isinstance(result, SqlPlanErrorSchema)
        assert not isinstance(result, SqlPlanSchema)

        # Verify error message is informative
        assert "timed out" in result.error.lower()
        assert "10.0s" in result.error

        # Verify confidence is 0.0 (no confidence in failed query)
        assert result.confidence == 0.0

    def test_sql_planner_suggests_retry_on_timeout(self):
        """Test that timeout error message suggests user action."""
        # Arrange
        provider = MockProvider(should_timeout=True)
        planner = SqlPlanner(provider)

        # Act
        result = planner.plan("Complex aggregation query", timeout=5.0)

        # Assert: Error message should be actionable
        assert isinstance(result, SqlPlanErrorSchema)
        assert "simpler query" in result.error.lower() or "increase timeout" in result.error.lower()

    def test_sql_planner_succeeds_when_no_timeout(self):
        """Test that normal queries work when timeout is not triggered."""
        # Arrange: Create provider that returns valid SQL
        provider = MockProvider(
            should_timeout=False,
            response_data={
                "sql": "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100",
                "confidence": 0.95,
                "explanation": "Aggregates revenue by region"
            }
        )
        planner = SqlPlanner(provider)

        # Act
        result = planner.plan("Show revenue by region", timeout=30.0)

        # Assert: Should return valid plan, not error
        assert isinstance(result, SqlPlanSchema)
        assert not isinstance(result, SqlPlanErrorSchema)
        assert result.confidence == 0.95
        assert "SELECT" in result.sql

    def test_timeout_does_not_hang_system(self, clean_query_history):
        """Test that timeout actually prevents hanging (finishes quickly)."""
        import time

        # Arrange: Provider configured to timeout
        provider = MockProvider(should_timeout=True)
        planner = SqlPlanner(provider)

        # Act: Measure execution time
        start = time.time()
        result = planner.plan("test query", timeout=1.0, bypass_cache=True)
        elapsed = time.time() - start

        # Assert: Should finish almost immediately (mock doesn't actually wait)
        # Real timeout would take 1s, but mock should be instant
        assert elapsed < 0.5, "Timeout handling took too long"
        assert isinstance(result, SqlPlanErrorSchema)

    def test_different_timeout_values(self):
        """Test that planner accepts different timeout configurations."""
        # Arrange
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )
        planner = SqlPlanner(provider)

        # Act & Assert: Different timeout values should work
        result1 = planner.plan("test", timeout=5.0)
        assert isinstance(result1, SqlPlanSchema)

        result2 = planner.plan("test", timeout=60.0)
        assert isinstance(result2, SqlPlanSchema)

        result3 = planner.plan("test", timeout=0.5)
        assert isinstance(result3, SqlPlanSchema)

    def test_timeout_error_classification(self, clean_query_history):
        """Test that timeout errors are distinct from other errors."""
        # Arrange
        timeout_provider = MockProvider(should_timeout=True)
        failure_provider = MockProvider(should_fail=True)

        timeout_planner = SqlPlanner(timeout_provider)
        failure_planner = SqlPlanner(failure_provider)

        # Act
        timeout_result = timeout_planner.plan("test", timeout=5.0, bypass_cache=True)
        failure_result = failure_planner.plan("test", bypass_cache=True)

        # Assert: Both return errors, but with different messages
        assert isinstance(timeout_result, SqlPlanErrorSchema)
        assert isinstance(failure_result, SqlPlanErrorSchema)

        # Timeout error should mention timeout
        assert "timeout" in timeout_result.error.lower()

        # Regular failure should NOT mention timeout
        assert "timeout" not in failure_result.error.lower()


class TestTimeoutIntegration:
    """Integration tests for timeout behavior."""

    def test_default_timeout_value(self):
        """Test that default timeout is reasonable (30s for planner)."""
        # Arrange
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )
        planner = SqlPlanner(provider)

        # Act: Call without explicit timeout (should use default)
        result = planner.plan("test query")

        # Assert: Should work with default timeout
        assert isinstance(result, SqlPlanSchema)

    def test_timeout_preserves_deterministic_validator_authority(self):
        """
        Week 4 Requirement: Preserve deterministic SQL validator authority.

        Even with timeout protection, the LLM still proposes and the
        deterministic validator still approves. Timeout just adds a
        time-based safety layer.
        """
        # Arrange: Provider returns SQL that will need validation
        provider = MockProvider(
            response_data={
                "sql": "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 100",
                "confidence": 0.95,
                "explanation": "Safe query with LIMIT"
            }
        )
        planner = SqlPlanner(provider)

        # Act
        result = planner.plan("show revenue", timeout=10.0)

        # Assert: SQL is generated (LLM proposes)
        assert isinstance(result, SqlPlanSchema)
        assert "SELECT" in result.sql
        assert "LIMIT" in result.sql  # Required by validator

        # Note: Actual validation happens in SqlTool.run(), not here
        # This test confirms timeout doesn't bypass the normal flow
