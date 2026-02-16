"""Base classes for LLM provider abstraction.

This module defines the interface for LLM providers that generate structured
outputs. All providers must implement the LLMProvider protocol.

Week 3 Commit 16: LLM Abstraction Layer
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar, Type
from pydantic import BaseModel


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
    """Base exception for LLM-related errors."""
    pass


class StructuredOutputError(LLMError):
    """Raised when LLM output cannot be parsed into the expected schema."""
    pass


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
        response_schema: Type[T]
    ) -> tuple[T, LLMUsage]:
        """Generate structured output from the LLM.

        Args:
            prompt: The prompt to send to the LLM
            response_schema: Pydantic model class for response validation

        Returns:
            Tuple of (validated_response, usage_stats)

        Raises:
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
            ...     SqlPlan
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
