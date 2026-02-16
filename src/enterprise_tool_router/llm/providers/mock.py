"""Mock LLM provider for testing.

This provider returns predefined responses without making actual API calls.
Used for unit testing the LLM abstraction layer.

Week 3 Commit 16: LLM Abstraction Layer
"""
from typing import Type, TypeVar
from pydantic import BaseModel

from ..base import LLMProvider, LLMUsage, StructuredOutputError


T = TypeVar('T', bound=BaseModel)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing.

    Returns predefined responses based on configured behavior.
    Useful for testing without making real API calls.

    Example:
        >>> from pydantic import BaseModel
        >>> class TestSchema(BaseModel):
        ...     message: str
        >>> provider = MockProvider(
        ...     response_data={"message": "test"}
        ... )
        >>> result, usage = provider.generate_structured("prompt", TestSchema)
        >>> assert result.message == "test"
    """

    def __init__(
        self,
        response_data: dict | None = None,
        should_fail: bool = False,
        input_tokens: int = 100,
        output_tokens: int = 50
    ):
        """Initialize mock provider.

        Args:
            response_data: Dict to return as structured response
            should_fail: If True, raise StructuredOutputError
            input_tokens: Mock input token count
            output_tokens: Mock output token count
        """
        self._response_data = response_data or {}
        self._should_fail = should_fail
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T]
    ) -> tuple[T, LLMUsage]:
        """Generate mock structured output.

        Args:
            prompt: The prompt (ignored in mock)
            response_schema: Pydantic model to validate against

        Returns:
            Tuple of (validated_response, mock_usage)

        Raises:
            StructuredOutputError: If should_fail is True or validation fails
        """
        if self._should_fail:
            raise StructuredOutputError("Mock provider configured to fail")

        try:
            # Validate response data against schema
            validated = response_schema(**self._response_data)
        except Exception as e:
            raise StructuredOutputError(f"Mock data validation failed: {e}")

        # Create mock usage stats
        usage = LLMUsage(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            total_tokens=self._input_tokens + self._output_tokens,
            estimated_cost_usd=0.001  # Mock cost
        )

        return validated, usage

    @property
    def model_name(self) -> str:
        """Return mock model identifier."""
        return "mock-llm-v1"
