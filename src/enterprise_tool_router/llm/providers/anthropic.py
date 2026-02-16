"""Anthropic (Claude) LLM provider.

This provider integrates with Anthropic's Claude API for structured output
generation using the Messages API with JSON mode.

Week 3 Commit 16: LLM Abstraction Layer
"""
import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel

from ..base import LLMProvider, LLMUsage, LLMError, StructuredOutputError


T = TypeVar('T', bound=BaseModel)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider.

    Requires ANTHROPIC_API_KEY environment variable.

    Pricing (as of 2024-01-15):
    - Claude 3.5 Sonnet: $3.00/MTok input, $15.00/MTok output

    Example:
        >>> import os
        >>> os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
        >>> provider = AnthropicProvider()
        >>> from pydantic import BaseModel
        >>> class Response(BaseModel):
        ...     answer: str
        >>> result, usage = provider.generate_structured(
        ...     "What is 2+2?",
        ...     Response
        ... )
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """Initialize Anthropic provider.

        Args:
            model: Model to use (default: from ANTHROPIC_MODEL env var or claude-3-5-sonnet-20241022)
            api_key: API key (default: from ANTHROPIC_API_KEY env var)

        Raises:
            LLMError: If API key is not provided
        """
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise LLMError("ANTHROPIC_API_KEY environment variable not set")

        self._model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

        # Lazy import to avoid requiring anthropic package if not used
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        except ImportError:
            raise LLMError("anthropic package not installed. Run: pip install anthropic")

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T]
    ) -> tuple[T, LLMUsage]:
        """Generate structured output using Claude.

        Uses Claude's JSON mode to ensure valid JSON output.

        Args:
            prompt: The prompt to send to Claude
            response_schema: Pydantic model for response validation

        Returns:
            Tuple of (validated_response, usage_stats)

        Raises:
            StructuredOutputError: If Claude output doesn't match schema
            LLMError: For API errors
        """
        try:
            # Build system prompt with schema instructions
            schema_json = response_schema.model_json_schema()
            system_prompt = (
                f"You must respond with valid JSON matching this schema:\n"
                f"{json.dumps(schema_json, indent=2)}\n\n"
                f"Respond with ONLY the JSON object, no other text."
            )

            # Call Claude API
            message = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract text content
            if not message.content or len(message.content) == 0:
                raise StructuredOutputError("Empty response from Claude")

            response_text = message.content[0].text

            # Parse and validate JSON
            try:
                response_data = json.loads(response_text)
                validated = response_schema(**response_data)
            except json.JSONDecodeError as e:
                raise StructuredOutputError(f"Invalid JSON from Claude: {e}")
            except Exception as e:
                raise StructuredOutputError(f"Schema validation failed: {e}")

            # Calculate usage and cost
            usage = self._calculate_usage(message.usage)

            return validated, usage

        except StructuredOutputError:
            raise
        except Exception as e:
            raise LLMError(f"Anthropic API error: {e}")

    def _calculate_usage(self, usage_obj) -> LLMUsage:
        """Calculate token usage and estimated cost.

        Args:
            usage_obj: Anthropic usage object

        Returns:
            LLMUsage with cost estimate
        """
        input_tokens = usage_obj.input_tokens
        output_tokens = usage_obj.output_tokens
        total_tokens = input_tokens + output_tokens

        # Claude 3.5 Sonnet pricing (per million tokens)
        input_cost_per_mtok = 3.00
        output_cost_per_mtok = 15.00

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
        """Return the Claude model being used."""
        return self._model
