"""Structured Error Taxonomy for Enterprise Tool Router.

Week 4 Commit 25: Structured Error Taxonomy

This module provides a comprehensive error classification system with:
- Hierarchical error categories (Planning, Validation, Execution, etc.)
- Severity levels (INFO, WARNING, ERROR, CRITICAL)
- Retryability indicators
- Structured JSON serialization for all errors

All errors in the system inherit from StructuredError and provide:
- Consistent to_dict() method for JSON serialization
- Error category and severity metadata
- Human-readable messages with context
- Machine-parseable error codes

Example:
    >>> try:
    ...     raise PlannerError("Failed to generate SQL", details={"query": "..."})
    ... except StructuredError as e:
    ...     error_json = e.to_dict()
    ...     print(error_json["error_type"])
    ...     print(error_json["category"])
    ...     print(error_json["severity"])
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone


class ErrorCategory(Enum):
    """Error categories for classification.

    Week 4 Commit 25: Structured taxonomy for error handling.
    """
    PLANNING = "planning"           # LLM planning/generation errors
    VALIDATION = "validation"       # Schema/input validation errors
    EXECUTION = "execution"         # Tool execution errors (SQL, REST, etc.)
    TIMEOUT = "timeout"            # Timeout/cancellation errors
    RATE_LIMIT = "rate_limit"      # Rate limiting errors
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker errors
    CACHE = "cache"                # Cache errors
    CONFIGURATION = "configuration"  # Configuration/setup errors
    UNKNOWN = "unknown"            # Unclassified errors


class ErrorSeverity(Enum):
    """Error severity levels.

    Week 4 Commit 25: Consistent severity classification.
    """
    INFO = "info"          # Informational (e.g., cache miss)
    WARNING = "warning"    # Warning (e.g., low confidence)
    ERROR = "error"        # Error (e.g., validation failed)
    CRITICAL = "critical"  # Critical (e.g., system failure)


class StructuredError(Exception):
    """Base class for all structured errors.

    Week 4 Commit 25: All errors return predictable JSON schema.

    Provides consistent structure for error handling and serialization.
    All errors include category, severity, retryability, and context.

    Attributes:
        message: Human-readable error message
        category: ErrorCategory classification
        severity: ErrorSeverity level
        retryable: Whether the operation can be retried
        details: Additional context (dict)
        timestamp: When the error occurred

    Example:
        >>> error = StructuredError(
        ...     "Something went wrong",
        ...     category=ErrorCategory.EXECUTION,
        ...     severity=ErrorSeverity.ERROR,
        ...     retryable=True,
        ...     details={"user_id": "123"}
        ... )
        >>> error_dict = error.to_dict()
        >>> assert error_dict["error_type"] == "StructuredError"
        >>> assert error_dict["retryable"] is True
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize structured error.

        Args:
            message: Human-readable error message
            category: Error category (default: UNKNOWN)
            severity: Error severity (default: ERROR)
            retryable: Whether operation can be retried (default: False)
            details: Additional context dictionary (default: None)
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.retryable = retryable
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to structured dictionary.

        Returns:
            Dictionary with error details in predictable schema:
            {
                "error_type": "ErrorClassName",
                "message": "Human-readable message",
                "category": "planning|validation|execution|...",
                "severity": "info|warning|error|critical",
                "retryable": true|false,
                "details": {...},
                "timestamp": "2024-01-01T12:00:00.000000"
            }
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "retryable": self.retryable,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class PlannerError(StructuredError):
    """Error during LLM planning/generation phase.

    Week 4 Commit 25: Structured error for planner failures.

    Raised when the LLM fails to generate a valid plan (SQL, etc.).
    Typically includes low confidence, malformed output, or API failures.

    Example:
        >>> raise PlannerError(
        ...     "LLM returned invalid SQL",
        ...     retryable=True,
        ...     details={"confidence": 0.3, "query": "..."}
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = True,  # Planning errors are often transient
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize planner error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: True)
            details: Additional context (LLM output, confidence, etc.)
        """
        super().__init__(
            message=message,
            category=ErrorCategory.PLANNING,
            severity=ErrorSeverity.ERROR,
            retryable=retryable,
            details=details
        )


class ValidationError(StructuredError):
    """Error during input/output validation.

    Week 4 Commit 25: Structured error for validation failures.

    Raised when input doesn't match schema, constraints are violated,
    or output fails validation checks (e.g., missing LIMIT in SQL).

    Example:
        >>> raise ValidationError(
        ...     "SQL missing required LIMIT clause",
        ...     retryable=False,
        ...     details={"sql": "SELECT * FROM users", "rule": "LIMIT required"}
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = False,  # Validation errors usually need input change
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize validation error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: False)
            details: Validation details (field, constraint, etc.)
        """
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            retryable=retryable,
            details=details
        )


class ExecutionError(StructuredError):
    """Error during tool execution.

    Week 4 Commit 25: Structured error for execution failures.

    Raised when a tool (SQL, REST, Vector) fails during execution.
    Includes database errors, API failures, network issues, etc.

    Example:
        >>> raise ExecutionError(
        ...     "Database connection failed",
        ...     retryable=True,
        ...     details={"db_host": "localhost", "error_code": "08006"}
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = True,  # Execution errors often transient (network, etc.)
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize execution error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: True)
            details: Execution context (tool, operation, etc.)
        """
        super().__init__(
            message=message,
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.ERROR,
            retryable=retryable,
            details=details
        )


class TimeoutError(StructuredError):
    """Error when operation exceeds timeout.

    Week 4 Commit 25: Structured error for timeout scenarios.

    Raised when an operation (LLM call, database query, API request)
    exceeds its configured timeout threshold.

    Example:
        >>> raise TimeoutError(
        ...     "LLM request exceeded 30s timeout",
        ...     retryable=True,
        ...     details={"timeout_seconds": 30, "operation": "generate_sql"}
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = True,  # Timeouts are often transient
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize timeout error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: True)
            details: Timeout details (duration, operation, etc.)
        """
        super().__init__(
            message=message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.WARNING,
            retryable=retryable,
            details=details
        )


class RateLimitError(StructuredError):
    """Error when rate limit exceeded.

    Week 4 Commit 25: Structured error for rate limiting.

    Raised when a user/IP exceeds configured rate limits.
    Includes retry_after guidance for client backoff.

    Example:
        >>> raise RateLimitError(
        ...     "Rate limit exceeded: 100 requests per 60s",
        ...     retryable=True,
        ...     details={
        ...         "identifier": "user123",
        ...         "limit": 100,
        ...         "window_seconds": 60,
        ...         "retry_after_seconds": 15.3
        ...     }
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = True,  # Can retry after waiting
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize rate limit error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: True)
            details: Rate limit details (limit, window, retry_after, etc.)
        """
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.WARNING,
            retryable=retryable,
            details=details
        )


class CircuitBreakerError(StructuredError):
    """Error when circuit breaker is open.

    Week 4 Commit 25: Structured error for circuit breaker state.

    Raised when circuit breaker prevents operation due to
    repeated failures. Indicates service is temporarily unavailable.

    Example:
        >>> raise CircuitBreakerError(
        ...     "LLM service unavailable (circuit breaker open)",
        ...     retryable=True,
        ...     details={
        ...         "state": "open",
        ...         "failure_count": 5,
        ...         "retry_after_seconds": 30
        ...     }
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = True,  # Can retry after recovery timeout
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize circuit breaker error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: True)
            details: Circuit breaker state and timing
        """
        super().__init__(
            message=message,
            category=ErrorCategory.CIRCUIT_BREAKER,
            severity=ErrorSeverity.WARNING,
            retryable=retryable,
            details=details
        )


class CacheError(StructuredError):
    """Error during cache operations.

    Week 4 Commit 25: Structured error for cache failures.

    Raised when cache operations fail (Redis connection, corruption, etc.).
    Usually non-fatal - system falls back to origin.

    Example:
        >>> raise CacheError(
        ...     "Redis connection failed",
        ...     retryable=True,
        ...     details={"backend": "redis", "operation": "get"}
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize cache error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: True)
            details: Cache operation details
        """
        super().__init__(
            message=message,
            category=ErrorCategory.CACHE,
            severity=ErrorSeverity.INFO,  # Cache errors usually non-fatal
            retryable=retryable,
            details=details
        )


class ConfigurationError(StructuredError):
    """Error in system configuration.

    Week 4 Commit 25: Structured error for configuration issues.

    Raised when required configuration is missing, invalid,
    or incompatible. Usually requires admin intervention.

    Example:
        >>> raise ConfigurationError(
        ...     "Missing required environment variable: DATABASE_URL",
        ...     retryable=False,
        ...     details={"variable": "DATABASE_URL"}
        ... )
    """

    def __init__(
        self,
        message: str,
        retryable: bool = False,  # Config errors need manual fix
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize configuration error.

        Args:
            message: Human-readable error message
            retryable: Whether to retry (default: False)
            details: Configuration details
        """
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            retryable=retryable,
            details=details
        )
