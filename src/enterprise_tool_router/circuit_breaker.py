"""Circuit Breaker pattern for LLM fault tolerance.

Week 4 Commit 22: Circuit Breaker (LLM)

Implements the Circuit Breaker pattern to prevent cascading failures when
LLM providers are experiencing issues. The circuit breaker tracks failures
and temporarily stops calling the LLM when a failure threshold is exceeded,
allowing the system to continue operating with fallback behavior.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped, requests fail fast without calling LLM
- HALF_OPEN: Testing recovery, limited requests allowed

Example:
    >>> from enterprise_tool_router.circuit_breaker import CircuitBreaker
    >>> breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
    >>>
    >>> if breaker.can_execute():
    ...     try:
    ...         result = call_llm()
    ...         breaker.record_success()
    ...     except Exception:
    ...         breaker.record_failure()
    ... else:
    ...     # Circuit is open, use fallback
    ...     result = fallback_behavior()
"""
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Circuit tripped, fail fast
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[datetime]
    opened_at: Optional[datetime]

    def to_dict(self) -> dict:
        """Convert stats to dictionary for logging/monitoring."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None
        }


class CircuitBreaker:
    """Circuit breaker for fault-tolerant LLM calls.

    Tracks failures in a sliding time window and opens the circuit when
    the failure threshold is exceeded. After a timeout, allows test requests
    to check if the service has recovered.

    Week 4 Commit 22: Prevents cascading failures from unreliable LLM providers.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        timeout_seconds: Time window for counting failures (sliding window)
        recovery_timeout: Seconds to wait before transitioning to half-open

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        >>>
        >>> # Normal operation
        >>> if breaker.can_execute():
        ...     try:
        ...         result = expensive_operation()
        ...         breaker.record_success()
        ...     except Exception as e:
        ...         breaker.record_failure()
        ...         # Use fallback
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
        recovery_timeout: float = 30.0
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit (default: 5)
            timeout_seconds: Time window for counting failures in seconds (default: 60)
            recovery_timeout: Seconds to wait before half-open state (default: 30)
        """
        self._failure_threshold = failure_threshold
        self._timeout_seconds = timeout_seconds
        self._recovery_timeout = recovery_timeout

        # State
        self._state = CircuitState.CLOSED
        self._failure_times: deque[datetime] = deque()
        self._opened_at: Optional[datetime] = None

        # Metrics
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        """Check if execution is allowed.

        Returns:
            True if request can proceed, False if circuit is open
        """
        self._update_state()

        if self._state == CircuitState.OPEN:
            return False

        # CLOSED or HALF_OPEN states allow execution
        return True

    def record_success(self) -> None:
        """Record a successful execution.

        In HALF_OPEN state, success closes the circuit.
        In CLOSED state, just increments success counter.
        """
        self._success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            # Success in half-open state closes the circuit
            self._close_circuit()

    def record_failure(self) -> None:
        """Record a failed execution.

        Increments failure count and may open the circuit if threshold exceeded.
        In HALF_OPEN state, failure immediately reopens the circuit.
        """
        now = datetime.now()
        self._failure_count += 1
        self._last_failure_time = now
        self._failure_times.append(now)

        # Remove old failures outside the time window
        self._remove_old_failures()

        if self._state == CircuitState.HALF_OPEN:
            # Failure in half-open state reopens the circuit
            self._open_circuit()
        elif self._state == CircuitState.CLOSED:
            # Check if we've exceeded the threshold
            if len(self._failure_times) >= self._failure_threshold:
                self._open_circuit()

    def reset(self) -> None:
        """Reset the circuit breaker to initial state.

        Useful for testing or manual recovery.
        """
        self._state = CircuitState.CLOSED
        self._failure_times.clear()
        self._opened_at = None
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    def get_stats(self) -> CircuitBreakerStats:
        """Get current circuit breaker statistics.

        Returns:
            CircuitBreakerStats with current state and metrics
        """
        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            opened_at=self._opened_at
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        self._update_state()
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN

    # Private methods

    def _update_state(self) -> None:
        """Update state based on current conditions.

        Transitions from OPEN to HALF_OPEN after recovery timeout.
        """
        if self._state == CircuitState.OPEN and self._opened_at:
            # Check if recovery timeout has elapsed
            elapsed = (datetime.now() - self._opened_at).total_seconds()
            if elapsed >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN

    def _open_circuit(self) -> None:
        """Open the circuit (stop allowing requests)."""
        self._state = CircuitState.OPEN
        self._opened_at = datetime.now()

    def _close_circuit(self) -> None:
        """Close the circuit (resume normal operation)."""
        self._state = CircuitState.CLOSED
        self._failure_times.clear()
        self._opened_at = None

    def _remove_old_failures(self) -> None:
        """Remove failures outside the sliding time window."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self._timeout_seconds)

        # Remove failures older than the time window
        while self._failure_times and self._failure_times[0] < cutoff:
            self._failure_times.popleft()
