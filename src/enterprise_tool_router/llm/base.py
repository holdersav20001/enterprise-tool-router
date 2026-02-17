"""Base classes for LLM provider abstraction.

This module defines the interface for LLM providers that generate structured
outputs. All providers must implement the LLMProvider protocol.

Week 3 Commit 16: LLM Abstraction Layer
Week 4 Commit 25: Structured error taxonomy integration
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar, Type, Optional, Dict, Any
from pydantic import BaseModel

# Week 4 Commit 25: Import structured error taxonomy
from ..errors import PlannerError, TimeoutError as StructuredTimeoutError, ValidationError


T = TypeVar('T', bound=BaseModel)


@dataclass(frozen=True)
class LLMUsage:
    """Token usage and cost tracking for LLM calls.

    Attributes:
        input_tokens: Number of tokens in the prompt
        output_tokens: Number of tokens in the response
        total_tokens: Total tokens used (input + output)
        estimated_cost_usd: Estimated cost in USD
    """
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class LLMError(Exception):
    """Base exception for LLM-related errors.

    Week 4 Commit 25: Base for backward compatibility.
    New code should use PlannerError from errors module.
    """
    pass


class StructuredOutputError(PlannerError):
    """Raised when LLM output cannot be parsed into the expected schema.

    Week 4 Commit 25: Now inherits from PlannerError for structured errors.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize structured output error.

        Args:
            message: Human-readable error message
            details: Additional context (output, schema, etc.)
        """
        super().__init__(
            message=message,
            retryable=True,  # LLM might succeed on retry
            details=details or {}
        )


class LLMTimeoutError(StructuredTimeoutError):
    """Raised when LLM request exceeds timeout threshold.

    Week 4 Commit 21: Timeout protection for LLM calls.
    Week 4 Commit 25: Now inherits from StructuredTimeoutError.
    This prevents the system from hanging on slow or unresponsive LLM providers.
    """

    def __init__(self, message: str, timeout_seconds: Optional[float] = None):
        """Initialize LLM timeout error.

        Args:
            message: Human-readable error message
            timeout_seconds: The timeout that was exceeded
        """
        details = {}
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(
            message=message,
            retryable=True,
            details=details
        )


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM providers (Anthropic, OpenAI, etc.) must implement this interface.
    Ensures consistent behavior across different LLM backends.

    Key Requirements:
    - Must return structured JSON validated against Pydantic schema
    - Must track token usage and cost
    - Must handle errors gracefully
    - Must not log raw prompts or responses (security)
    """

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        timeout: float = 60.0
    ) -> tuple[T, LLMUsage]:
        """Generate structured output from the LLM.

        Args:
            prompt: The prompt to send to the LLM
            response_schema: Pydantic model class for response validation
            timeout: Maximum time to wait for LLM response in seconds (default: 60.0)

        Returns:
            Tuple of (validated_response, usage_stats)

        Raises:
            LLMTimeoutError: If LLM request exceeds timeout
            StructuredOutputError: If LLM output doesn't match schema
            LLMError: For other LLM-related errors

        Example:
            >>> from pydantic import BaseModel
            >>> class SqlPlan(BaseModel):
            ...     sql: str
            ...     confidence: float
            >>> provider = AnthropicProvider()
            >>> result, usage = provider.generate_structured(
            ...     "Generate SQL for: show revenue by region",
            ...     SqlPlan,
            ...     timeout=30.0
            ... )
            >>> assert isinstance(result, SqlPlan)
            >>> assert 0.0 <= result.confidence <= 1.0
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier being used.

        Example: "claude-3-5-sonnet-20241022" or "gpt-4o"
        """
        pass
