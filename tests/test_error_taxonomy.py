"""Tests for Structured Error Taxonomy.

Week 4 Commit 25: Structured Error Taxonomy

This test suite validates that:
1. All errors inherit from StructuredError
2. All errors have predictable to_dict() schema
3. Error categories and severities are correct
4. Retryability is set appropriately
5. Details are preserved in serialization
6. Integration with existing code works
"""
import pytest
from datetime import datetime
from enterprise_tool_router.errors import (
    StructuredError,
    ErrorCategory,
    ErrorSeverity,
    PlannerError,
    ValidationError,
    ExecutionError,
    TimeoutError,
    RateLimitError,
    CircuitBreakerError,
    CacheError,
    ConfigurationError
)
from enterprise_tool_router.llm.base import LLMTimeoutError, StructuredOutputError
from enterprise_tool_router.rate_limiter import RateLimitError as RateLimiterError


class TestStructuredErrorBase:
    """Test base StructuredError functionality."""

    def test_structured_error_creation(self):
        """Test creating a basic structured error."""
        error = StructuredError(
            "Test error message",
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.ERROR,
            retryable=True,
            details={"key": "value"}
        )

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.EXECUTION
        assert error.severity == ErrorSeverity.ERROR
        assert error.retryable is True
        assert error.details == {"key": "value"}
        assert isinstance(error.timestamp, datetime)

    def test_structured_error_to_dict(self):
        """Test that to_dict() returns predictable schema."""
        error = StructuredError(
            "Test message",
            category=ErrorCategory.PLANNING,
            severity=ErrorSeverity.WARNING,
            retryable=False,
            details={"context": "test"}
        )

        error_dict = error.to_dict()

        # Validate schema
        assert "error_type" in error_dict
        assert "message" in error_dict
        assert "category" in error_dict
        assert "severity" in error_dict
        assert "retryable" in error_dict
        assert "details" in error_dict
        assert "timestamp" in error_dict

        # Validate values
        assert error_dict["error_type"] == "StructuredError"
        assert error_dict["message"] == "Test message"
        assert error_dict["category"] == "planning"
        assert error_dict["severity"] == "warning"
        assert error_dict["retryable"] is False
        assert error_dict["details"] == {"context": "test"}

    def test_structured_error_defaults(self):
        """Test that defaults are set correctly."""
        error = StructuredError("Simple error")

        assert error.category == ErrorCategory.UNKNOWN
        assert error.severity == ErrorSeverity.ERROR
        assert error.retryable is False
        assert error.details == {}

    def test_timestamp_is_utc(self):
        """Test that timestamp is in UTC."""
        error = StructuredError("Test")
        error_dict = error.to_dict()

        # Timestamp should be ISO format
        timestamp_str = error_dict["timestamp"]
        assert "T" in timestamp_str  # ISO format has T separator


class TestPlannerError:
    """Test PlannerError functionality."""

    def test_planner_error_defaults(self):
        """Test PlannerError has correct category and severity."""
        error = PlannerError("LLM failed to generate SQL")

        assert error.category == ErrorCategory.PLANNING
        assert error.severity == ErrorSeverity.ERROR
        assert error.retryable is True  # Planning errors default to retryable

    def test_planner_error_to_dict(self):
        """Test PlannerError serialization."""
        error = PlannerError(
            "Low confidence output",
            retryable=False,
            details={"confidence": 0.3}
        )

        error_dict = error.to_dict()
        assert error_dict["error_type"] == "PlannerError"
        assert error_dict["category"] == "planning"
        assert error_dict["retryable"] is False
        assert error_dict["details"]["confidence"] == 0.3


class TestValidationError:
    """Test ValidationError functionality."""

    def test_validation_error_defaults(self):
        """Test ValidationError has correct category and severity."""
        error = ValidationError("Missing LIMIT clause")

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.ERROR
        assert error.retryable is False  # Validation errors not retryable by default

    def test_validation_error_with_details(self):
        """Test ValidationError with validation details."""
        error = ValidationError(
            "Invalid input",
            details={"field": "query", "constraint": "not_empty"}
        )

        error_dict = error.to_dict()
        assert error_dict["error_type"] == "ValidationError"
        assert error_dict["category"] == "validation"
        assert error_dict["details"]["field"] == "query"


class TestExecutionError:
    """Test ExecutionError functionality."""

    def test_execution_error_defaults(self):
        """Test ExecutionError has correct category and severity."""
        error = ExecutionError("Database connection failed")

        assert error.category == ErrorCategory.EXECUTION
        assert error.severity == ErrorSeverity.ERROR
        assert error.retryable is True  # Execution errors often retryable

    def test_execution_error_with_context(self):
        """Test ExecutionError preserves execution context."""
        error = ExecutionError(
            "SQL execution failed",
            retryable=False,
            details={"error_code": "42P01", "table": "missing_table"}
        )

        error_dict = error.to_dict()
        assert error_dict["error_type"] == "ExecutionError"
        assert error_dict["details"]["error_code"] == "42P01"


class TestTimeoutError:
    """Test TimeoutError functionality."""

    def test_timeout_error_defaults(self):
        """Test TimeoutError has correct category and severity."""
        error = TimeoutError("Operation timed out")

        assert error.category == ErrorCategory.TIMEOUT
        assert error.severity == ErrorSeverity.WARNING  # Timeouts are warnings
        assert error.retryable is True

    def test_timeout_error_with_duration(self):
        """Test TimeoutError includes timeout duration."""
        error = TimeoutError(
            "Request exceeded timeout",
            details={"timeout_seconds": 30, "operation": "llm_call"}
        )

        error_dict = error.to_dict()
        assert error_dict["category"] == "timeout"
        assert error_dict["details"]["timeout_seconds"] == 30


class TestRateLimitError:
    """Test RateLimitError functionality."""

    def test_rate_limit_error_defaults(self):
        """Test RateLimitError has correct category and severity."""
        error = RateLimitError("Rate limit exceeded")

        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.severity == ErrorSeverity.WARNING
        assert error.retryable is True

    def test_rate_limit_error_with_retry_guidance(self):
        """Test RateLimitError includes retry_after."""
        error = RateLimitError(
            "Too many requests",
            details={
                "limit": 100,
                "window_seconds": 60,
                "retry_after_seconds": 15.5
            }
        )

        error_dict = error.to_dict()
        assert error_dict["category"] == "rate_limit"
        assert error_dict["details"]["retry_after_seconds"] == 15.5


class TestCircuitBreakerError:
    """Test CircuitBreakerError functionality."""

    def test_circuit_breaker_error_defaults(self):
        """Test CircuitBreakerError has correct category and severity."""
        error = CircuitBreakerError("Circuit breaker open")

        assert error.category == ErrorCategory.CIRCUIT_BREAKER
        assert error.severity == ErrorSeverity.WARNING
        assert error.retryable is True

    def test_circuit_breaker_error_with_state(self):
        """Test CircuitBreakerError includes breaker state."""
        error = CircuitBreakerError(
            "Service unavailable",
            details={"state": "open", "failure_count": 5}
        )

        error_dict = error.to_dict()
        assert error_dict["category"] == "circuit_breaker"
        assert error_dict["details"]["state"] == "open"


class TestCacheError:
    """Test CacheError functionality."""

    def test_cache_error_defaults(self):
        """Test CacheError has correct category and severity."""
        error = CacheError("Redis connection failed")

        assert error.category == ErrorCategory.CACHE
        assert error.severity == ErrorSeverity.INFO  # Cache errors are non-fatal
        assert error.retryable is True

    def test_cache_error_low_severity(self):
        """Test that cache errors are INFO level (non-critical)."""
        error = CacheError("Cache miss")
        error_dict = error.to_dict()

        assert error_dict["severity"] == "info"


class TestConfigurationError:
    """Test ConfigurationError functionality."""

    def test_configuration_error_defaults(self):
        """Test ConfigurationError has correct category and severity."""
        error = ConfigurationError("Missing DATABASE_URL")

        assert error.category == ErrorCategory.CONFIGURATION
        assert error.severity == ErrorSeverity.CRITICAL  # Config errors are critical
        assert error.retryable is False  # Need manual fix

    def test_configuration_error_critical_severity(self):
        """Test that config errors are CRITICAL."""
        error = ConfigurationError("Invalid configuration")
        error_dict = error.to_dict()

        assert error_dict["severity"] == "critical"
        assert error_dict["retryable"] is False


class TestBackwardCompatibility:
    """Test backward compatibility with existing error classes."""

    def test_llm_timeout_error_is_structured(self):
        """Test that LLMTimeoutError inherits from structured TimeoutError."""
        error = LLMTimeoutError("LLM timed out", timeout_seconds=30.0)

        # Should be instance of both
        assert isinstance(error, TimeoutError)

        # Should have structured error methods
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "LLMTimeoutError"
        assert error_dict["category"] == "timeout"
        assert error_dict["details"]["timeout_seconds"] == 30.0

    def test_structured_output_error_is_planner_error(self):
        """Test that StructuredOutputError inherits from PlannerError."""
        error = StructuredOutputError("Invalid JSON output")

        # Should be instance of PlannerError
        assert isinstance(error, PlannerError)

        # Should have structured error methods
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "StructuredOutputError"
        assert error_dict["category"] == "planning"

    def test_rate_limiter_error_is_structured(self):
        """Test that rate_limiter.RateLimitError is structured."""
        # This is the RateLimitError from rate_limiter.py
        error = RateLimiterError(
            identifier="user123",
            limit=100,
            window=60,
            retry_after=15.5
        )

        # Should have structured error methods
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "RateLimitError"
        assert error_dict["category"] == "rate_limit"

        # Should preserve backward-compatible attributes
        assert error.identifier == "user123"
        assert error.limit == 100
        assert error.window == 60
        assert error.retry_after == 15.5


class TestErrorSchemaConsistency:
    """Test that all errors return consistent schema.

    Acceptance Criteria: All errors return predictable schema.
    """

    def test_all_errors_have_same_keys(self):
        """Test that all error types return the same dictionary keys."""
        errors = [
            PlannerError("test"),
            ValidationError("test"),
            ExecutionError("test"),
            TimeoutError("test"),
            RateLimitError("test"),
            CircuitBreakerError("test"),
            CacheError("test"),
            ConfigurationError("test")
        ]

        expected_keys = {
            "error_type",
            "message",
            "category",
            "severity",
            "retryable",
            "details",
            "timestamp"
        }

        for error in errors:
            error_dict = error.to_dict()
            assert set(error_dict.keys()) == expected_keys, \
                f"{error.__class__.__name__} missing keys"

    def test_all_errors_have_valid_enums(self):
        """Test that all errors use valid enum values."""
        errors = [
            PlannerError("test"),
            ValidationError("test"),
            ExecutionError("test"),
            TimeoutError("test"),
            RateLimitError("test"),
            CircuitBreakerError("test"),
            CacheError("test"),
            ConfigurationError("test")
        ]

        valid_categories = {e.value for e in ErrorCategory}
        valid_severities = {e.value for e in ErrorSeverity}

        for error in errors:
            error_dict = error.to_dict()
            assert error_dict["category"] in valid_categories, \
                f"{error.__class__.__name__} has invalid category"
            assert error_dict["severity"] in valid_severities, \
                f"{error.__class__.__name__} has invalid severity"

    def test_all_errors_have_boolean_retryable(self):
        """Test that retryable is always boolean."""
        errors = [
            PlannerError("test"),
            ValidationError("test"),
            ExecutionError("test"),
            TimeoutError("test"),
            RateLimitError("test"),
            CircuitBreakerError("test"),
            CacheError("test"),
            ConfigurationError("test")
        ]

        for error in errors:
            error_dict = error.to_dict()
            assert isinstance(error_dict["retryable"], bool), \
                f"{error.__class__.__name__} retryable is not boolean"


class TestIntegrationWithRouter:
    """Test integration of error taxonomy with router."""

    def test_router_returns_structured_rate_limit_error(self):
        """Test that router returns structured error for rate limiting."""
        from enterprise_tool_router.router import ToolRouter
        from enterprise_tool_router.rate_limiter import RateLimiter

        # Create router with very low rate limit
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        router = ToolRouter(rate_limiter=limiter)

        # First request should succeed
        result1 = router.handle("test query", user_id="test_user")

        # Second request should be rate limited
        result2 = router.handle("test query", user_id="test_user")

        # Check that result is structured error
        error_data = result2.result.data
        assert "error_type" in error_data
        assert error_data["error_type"] == "RateLimitError"
        assert error_data["category"] == "rate_limit"
        assert error_data["retryable"] is True
        assert "retry_after_seconds" in error_data["details"]
