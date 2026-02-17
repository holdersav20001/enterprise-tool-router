"""Tests for Circuit Breaker pattern.

Week 4 Commit 22: Circuit Breaker (LLM)

This test suite validates that:
1. Circuit breaker tracks failures correctly
2. Circuit opens after threshold exceeded
3. Circuit transitions to half-open after recovery timeout
4. Circuit closes after successful request in half-open
5. Integration with SqlPlanner works correctly
"""
import pytest
import time
from datetime import datetime, timedelta
from enterprise_tool_router.circuit_breaker import CircuitBreaker, CircuitState
from enterprise_tool_router.sql_planner import SqlPlanner
from enterprise_tool_router.llm.providers import MockProvider
from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema, SqlPlanErrorSchema


class TestCircuitBreakerBasics:
    """Test basic circuit breaker functionality."""

    def test_initial_state_is_closed(self):
        """Test that circuit starts in closed state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    def test_can_execute_when_closed(self):
        """Test that execution is allowed in closed state."""
        breaker = CircuitBreaker()
        assert breaker.can_execute() is True

    def test_record_success_increments_counter(self):
        """Test that successes are counted."""
        breaker = CircuitBreaker()
        breaker.record_success()
        breaker.record_success()

        stats = breaker.get_stats()
        assert stats.success_count == 2

    def test_record_failure_increments_counter(self):
        """Test that failures are counted."""
        breaker = CircuitBreaker()
        breaker.record_failure()
        breaker.record_failure()

        stats = breaker.get_stats()
        assert stats.failure_count == 2

    def test_reset_clears_all_state(self):
        """Test that reset restores initial state."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Trigger some failures
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()

        # Reset
        breaker.reset()

        stats = breaker.get_stats()
        assert stats.state == CircuitState.CLOSED
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.last_failure_time is None


class TestCircuitBreakerThreshold:
    """Test circuit opening when threshold is exceeded."""

    def test_circuit_opens_after_threshold(self):
        """Test that circuit opens after failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60.0)

        # Record failures below threshold
        breaker.record_failure()
        assert breaker.is_closed

        breaker.record_failure()
        assert breaker.is_closed

        # Third failure should open circuit
        breaker.record_failure()
        assert breaker.is_open

    def test_can_execute_returns_false_when_open(self):
        """Test that execution is blocked when circuit is open."""
        breaker = CircuitBreaker(failure_threshold=2)

        breaker.record_failure()
        breaker.record_failure()

        assert breaker.is_open
        assert breaker.can_execute() is False

    def test_sliding_window_removes_old_failures(self):
        """Test that failures outside time window don't count."""
        # Very short timeout for testing
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=0.1)

        # Record 2 failures
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_closed

        # Wait for failures to expire
        time.sleep(0.15)

        # Record one more failure - should NOT open circuit
        # because old failures have expired
        breaker.record_failure()
        assert breaker.is_closed  # Only 1 failure in window

    def test_stats_reflect_current_state(self):
        """Test that stats accurately reflect circuit state."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Closed state
        stats = breaker.get_stats()
        assert stats.state == CircuitState.CLOSED
        assert stats.opened_at is None

        # Open circuit
        breaker.record_failure()
        breaker.record_failure()

        stats = breaker.get_stats()
        assert stats.state == CircuitState.OPEN
        assert stats.opened_at is not None
        assert stats.failure_count == 2


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery (half-open state)."""

    def test_circuit_transitions_to_half_open(self):
        """Test that circuit becomes half-open after recovery timeout."""
        # Very short recovery timeout for testing
        breaker = CircuitBreaker(
            failure_threshold=2,
            timeout_seconds=60.0,
            recovery_timeout=0.1  # 100ms
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should transition to half-open
        assert breaker.is_half_open

    def test_success_in_half_open_closes_circuit(self):
        """Test that success in half-open state closes the circuit."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open

        # Wait for half-open
        time.sleep(0.15)
        assert breaker.is_half_open

        # Success should close circuit
        breaker.record_success()
        assert breaker.is_closed

    def test_failure_in_half_open_reopens_circuit(self):
        """Test that failure in half-open state reopens the circuit."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open

        # Wait for half-open
        time.sleep(0.15)
        assert breaker.is_half_open

        # Failure should reopen circuit
        breaker.record_failure()
        assert breaker.is_open

    def test_can_execute_allowed_in_half_open(self):
        """Test that execution is allowed in half-open state."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Open circuit
        breaker.record_failure()
        breaker.record_failure()

        # Wait for half-open
        time.sleep(0.15)

        # Execution should be allowed
        assert breaker.can_execute() is True


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with SqlPlanner."""

    def test_planner_with_circuit_breaker(self):
        """Test that SqlPlanner uses circuit breaker."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )
        breaker = CircuitBreaker(failure_threshold=2)
        planner = SqlPlanner(provider, circuit_breaker=breaker)

        # Should work normally
        result = planner.plan("test query")
        assert isinstance(result, SqlPlanSchema)

        # Success should be recorded
        stats = breaker.get_stats()
        assert stats.success_count == 1

    def test_planner_records_failures(self):
        """Test that planner records failures in circuit breaker."""
        provider = MockProvider(should_fail=True)
        breaker = CircuitBreaker(failure_threshold=3)
        planner = SqlPlanner(provider, circuit_breaker=breaker)

        # First failure
        result = planner.plan("test")
        assert isinstance(result, SqlPlanErrorSchema)
        assert breaker.is_closed

        # Second failure
        result = planner.plan("test")
        assert isinstance(result, SqlPlanErrorSchema)
        assert breaker.is_closed

        # Third failure should open circuit
        result = planner.plan("test")
        assert breaker.is_open

    def test_planner_fails_fast_when_circuit_open(self):
        """Test that planner returns error immediately when circuit is open."""
        provider = MockProvider(should_fail=True)
        breaker = CircuitBreaker(failure_threshold=2)
        planner = SqlPlanner(provider, circuit_breaker=breaker)

        # Open the circuit
        planner.plan("test")
        planner.plan("test")
        assert breaker.is_open

        # Next call should fail fast without calling provider
        result = planner.plan("test")
        assert isinstance(result, SqlPlanErrorSchema)
        assert "circuit breaker" in result.error.lower()
        assert "temporarily unavailable" in result.error.lower()

    def test_planner_timeout_counted_as_failure(self):
        """Test that timeout errors trigger circuit breaker."""
        provider = MockProvider(should_timeout=True)
        breaker = CircuitBreaker(failure_threshold=2)
        planner = SqlPlanner(provider, circuit_breaker=breaker)

        # Timeouts should count as failures
        planner.plan("test", timeout=5.0)
        assert breaker.is_closed

        planner.plan("test", timeout=5.0)
        assert breaker.is_open  # Circuit should open

    def test_planner_creates_default_breaker_if_none(self):
        """Test that planner creates default circuit breaker."""
        provider = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )
        # No circuit breaker provided
        planner = SqlPlanner(provider)

        # Should still work (uses default breaker)
        result = planner.plan("test")
        assert isinstance(result, SqlPlanSchema)

    def test_system_continues_operating_when_circuit_open(self):
        """
        Acceptance Criteria: System continues operating safely when circuit is open.

        This is the key requirement - the system doesn't crash,
        it just returns graceful errors.
        """
        provider = MockProvider(should_fail=True)
        breaker = CircuitBreaker(failure_threshold=2)
        planner = SqlPlanner(provider, circuit_breaker=breaker)

        # Open the circuit by failing
        planner.plan("test")
        planner.plan("test")
        assert breaker.is_open

        # System should still handle requests gracefully
        for _ in range(10):
            result = planner.plan("test")
            assert isinstance(result, SqlPlanErrorSchema)
            assert "temporarily unavailable" in result.error.lower()
            # No exceptions raised - system continues operating

    def test_circuit_recovery_workflow(self):
        """Test complete recovery workflow: closed -> open -> half-open -> closed."""
        provider_failing = MockProvider(should_fail=True)
        provider_working = MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 10",
                "confidence": 0.9,
                "explanation": "Test"
            }
        )

        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Start with failing provider
        planner = SqlPlanner(provider_failing, circuit_breaker=breaker)

        # Closed -> Open
        planner.plan("test")
        planner.plan("test")
        assert breaker.is_open

        # Wait for half-open
        time.sleep(0.15)
        assert breaker.is_half_open

        # Switch to working provider (simulating service recovery)
        planner._llm = provider_working

        # Half-open -> Closed
        result = planner.plan("test")
        assert isinstance(result, SqlPlanSchema)
        assert breaker.is_closed

        # Circuit is now healthy again
        result = planner.plan("test")
        assert isinstance(result, SqlPlanSchema)
