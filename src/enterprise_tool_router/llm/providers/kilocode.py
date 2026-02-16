"""Kilocode LLM provider.

This provider integrates with Kilocode's API for structured output generation.
Kilocode uses an OpenRouter-compatible API endpoint with structured output support.

Week 3 Commit 21: Kilocode Provider Integration
"""
import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel
import requests

from ..base import LLMProvider, LLMUsage, LLMError, StructuredOutputError


T = TypeVar('T', bound=BaseModel)


class KilocodeProvider(LLMProvider):
    """Kilocode API provider.

    Requires KILOCODE_API_KEY environment variable or explicit API key.

    The Kilocode API uses an OpenRouter-compatible endpoint and supports
    structured output generation via JSON schema.

    Example:
        >>> import os
        >>> os.environ["KILOCODE_API_KEY"] = "eyJhbGci..."
        >>> provider = KilocodeProvider()
        >>> from pydantic import BaseModel
        >>> class Response(BaseModel):
        ...     answer: str
        >>> result, usage = provider.generate_structured(
        ...     "What is 2+2?",
        ...     Response
        ... )
    """

    # Kilocode API endpoint (OpenRouter-compatible)
    API_ENDPOINT = "https://kilocode.ai/api/openrouter/chat/completions"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """Initialize Kilocode provider.

        Args:
            model: Model to use (default: from KILOCODE_MODEL env var or google/gemini-2.5-flash-preview-05-20)
            api_key: API key (default: from KILOCODE_API_KEY env var)

        Raises:
            LLMError: If API key is not provided
        """
        self._api_key = api_key or os.getenv("KILOCODE_API_KEY")
        if not self._api_key:
            raise LLMError("KILOCODE_API_KEY environment variable not set or api_key not provided")

        # Default model - can be overridden via environment variable
        self._model = model or os.getenv("KILOCODE_MODEL", "google/gemini-2.5-flash-preview-05-20")

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T]
    ) -> tuple[T, LLMUsage]:
        """Generate structured output using Kilocode.

        Uses Kilocode's OpenRouter-compatible API with JSON schema mode
        to ensure valid JSON output matching the Pydantic schema.

        Args:
            prompt: The prompt to send to Kilocode
            response_schema: Pydantic model for response validation

        Returns:
            Tuple of (validated_response, usage_stats)

        Raises:
            StructuredOutputError: If Kilocode output doesn't match schema
            LLMError: For API errors
        """
        try:
            # Convert Pydantic schema to JSON Schema
            schema_json = response_schema.model_json_schema()

            # Build request payload with structured output
            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_schema.__name__,
                        "strict": True,
                        "schema": schema_json
                    }
                }
            }

            # Make API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}"
            }

            response = requests.post(
                self.API_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=60
            )

            # Check for HTTP errors
            if response.status_code != 200:
                raise LLMError(
                    f"Kilocode API returned status {response.status_code}: {response.text}"
                )

            # Parse response
            response_data = response.json()

            # Extract content from response
            if not response_data.get("choices") or len(response_data["choices"]) == 0:
                raise StructuredOutputError("Empty response from Kilocode")

            content = response_data["choices"][0]["message"]["content"]

            # Parse and validate JSON
            try:
                response_json = json.loads(content)
                validated = response_schema(**response_json)
            except json.JSONDecodeError as e:
                raise StructuredOutputError(f"Invalid JSON from Kilocode: {e}")
            except Exception as e:
                raise StructuredOutputError(f"Schema validation failed: {e}")

            # Calculate usage and cost
            usage = self._calculate_usage(response_data.get("usage", {}))

            return validated, usage

        except StructuredOutputError:
            raise
        except requests.exceptions.RequestException as e:
            raise LLMError(f"Kilocode API request failed: {e}")
        except Exception as e:
            raise LLMError(f"Kilocode API error: {e}")

    def _calculate_usage(self, usage_obj: dict) -> LLMUsage:
        """Calculate token usage and estimated cost.

        Args:
            usage_obj: OpenRouter usage object containing token counts and cost

        Returns:
            LLMUsage with cost estimate
        """
        input_tokens = usage_obj.get("prompt_tokens", 0)
        output_tokens = usage_obj.get("completion_tokens", 0)
        total_tokens = usage_obj.get("total_tokens", input_tokens + output_tokens)

        # Extract cost from usage object if available
        # OpenRouter returns cost in the usage object
        estimated_cost = usage_obj.get("cost", 0.0)

        return LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost
        )

    @property
    def model_name(self) -> str:
        """Return the Kilocode model being used."""
        return self._model
