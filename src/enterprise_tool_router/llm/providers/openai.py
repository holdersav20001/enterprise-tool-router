"""OpenAI LLM provider.

This provider integrates with OpenAI's API for structured output generation
using the Chat Completions API with JSON mode.

Week 3 Commit 16: LLM Abstraction Layer
"""
import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel

from ..base import LLMProvider, LLMUsage, LLMError, StructuredOutputError


T = TypeVar('T', bound=BaseModel)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider.

    Requires OPENAI_API_KEY environment variable.

    Pricing (as of 2024-01-15):
    - GPT-4o: $2.50/MTok input, $10.00/MTok output

    Example:
        >>> import os
        >>> os.environ["OPENAI_API_KEY"] = "sk-..."
        >>> provider = OpenAIProvider()
        >>> from pydantic import BaseModel
        >>> class Response(BaseModel):
        ...     answer: str
        >>> result, usage = provider.generate_structured(
        ...     "What is 2+2?",
        ...     Response
        ... )
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """Initialize OpenAI provider.

        Args:
            model: Model to use (default: from OPENAI_MODEL env var or gpt-4o)
            api_key: API key (default: from OPENAI_API_KEY env var)

        Raises:
            LLMError: If API key is not provided
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise LLMError("OPENAI_API_KEY environment variable not set")

        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

        # Lazy import to avoid requiring openai package if not used
        try:
            import openai
            self._client = openai.OpenAI(api_key=self._api_key)
        except ImportError:
            raise LLMError("openai package not installed. Run: pip install openai")

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T]
    ) -> tuple[T, LLMUsage]:
        """Generate structured output using OpenAI.

        Uses OpenAI's JSON mode to ensure valid JSON output.

        Args:
            prompt: The prompt to send to OpenAI
            response_schema: Pydantic model for response validation

        Returns:
            Tuple of (validated_response, usage_stats)

        Raises:
            StructuredOutputError: If OpenAI output doesn't match schema
            LLMError: For API errors
        """
        try:
            # Build system prompt with schema instructions
            schema_json = response_schema.model_json_schema()
            system_content = (
                f"You must respond with valid JSON matching this schema:\n"
                f"{json.dumps(schema_json, indent=2)}\n\n"
                f"Respond with ONLY the JSON object, no other text."
            )

            # Call OpenAI API with JSON mode
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=4096
            )

            # Extract content
            if not response.choices or len(response.choices) == 0:
                raise StructuredOutputError("Empty response from OpenAI")

            response_text = response.choices[0].message.content

            # Parse and validate JSON
            try:
                response_data = json.loads(response_text)
                validated = response_schema(**response_data)
            except json.JSONDecodeError as e:
                raise StructuredOutputError(f"Invalid JSON from OpenAI: {e}")
            except Exception as e:
                raise StructuredOutputError(f"Schema validation failed: {e}")

            # Calculate usage and cost
            usage = self._calculate_usage(response.usage)

            return validated, usage

        except StructuredOutputError:
            raise
        except Exception as e:
            raise LLMError(f"OpenAI API error: {e}")

    def _calculate_usage(self, usage_obj) -> LLMUsage:
        """Calculate token usage and estimated cost.

        Args:
            usage_obj: OpenAI usage object

        Returns:
            LLMUsage with cost estimate
        """
        input_tokens = usage_obj.prompt_tokens
        output_tokens = usage_obj.completion_tokens
        total_tokens = usage_obj.total_tokens

        # GPT-4o pricing (per million tokens)
        input_cost_per_mtok = 2.50
        output_cost_per_mtok = 10.00

        estimated_cost = (
            (input_tokens / 1_000_000) * input_cost_per_mtok +
            (output_tokens / 1_000_000) * output_cost_per_mtok
        )

        return LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost
        )

    @property
    def model_name(self) -> str:
        """Return the OpenAI model being used."""
        return self._model
