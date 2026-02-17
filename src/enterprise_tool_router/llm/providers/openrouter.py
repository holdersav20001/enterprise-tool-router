"""OpenRouter LLM provider.

This provider integrates with OpenRouter's API for structured output generation.
OpenRouter provides access to 200+ AI models through a single API.

Week 3 Commit 22: OpenRouter Provider Integration
"""
import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel
import requests

from ..base import LLMProvider, LLMUsage, LLMError, StructuredOutputError, LLMTimeoutError


T = TypeVar('T', bound=BaseModel)


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider.

    Requires OPENROUTER_API_KEY environment variable or explicit API key.

    OpenRouter provides access to 200+ AI models including Claude, GPT-4,
    Gemini, and many others through a unified API with structured output support.

    Example:
        >>> import os
        >>> os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-..."
        >>> provider = OpenRouterProvider(model="openrouter/aurora-alpha")
        >>> from pydantic import BaseModel
        >>> class Response(BaseModel):
        ...     answer: str
        >>> result, usage = provider.generate_structured(
        ...     "What is 2+2?",
        ...     Response
        ... )
    """

    # OpenRouter API endpoint
    API_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """Initialize OpenRouter provider.

        Args:
            model: Model to use (default: from OPENROUTER_MODEL env var or openrouter/aurora-alpha)
            api_key: API key (default: from OPENROUTER_API_KEY env var)

        Raises:
            LLMError: If API key is not provided
        """
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self._api_key:
            raise LLMError("OPENROUTER_API_KEY environment variable not set or api_key not provided")

        # Default model - can be overridden via environment variable
        self._model = model or os.getenv("OPENROUTER_MODEL", "openrouter/aurora-alpha")

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        timeout: float = 60.0
    ) -> tuple[T, LLMUsage]:
        """Generate structured output using OpenRouter.

        Uses OpenRouter's API with JSON schema mode to ensure valid JSON
        output matching the Pydantic schema.

        Args:
            prompt: The prompt to send to OpenRouter
            response_schema: Pydantic model for response validation
            timeout: Maximum time to wait for response in seconds (default: 60.0)

        Returns:
            Tuple of (validated_response, usage_stats)

        Raises:
            LLMTimeoutError: If request exceeds timeout
            StructuredOutputError: If OpenRouter output doesn't match schema
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

            # Make API request with proper OpenRouter authentication
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "https://github.com/holdersav20001/enterprise-tool-router",
                "X-Title": "Enterprise Tool Router"
            }

            response = requests.post(
                self.API_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=timeout
            )

            # Check for HTTP errors
            if response.status_code != 200:
                raise LLMError(
                    f"OpenRouter API returned status {response.status_code}: {response.text}"
                )

            # Parse response
            response_data = response.json()

            # Extract content from response
            if not response_data.get("choices") or len(response_data["choices"]) == 0:
                raise StructuredOutputError("Empty response from OpenRouter")

            content = response_data["choices"][0]["message"]["content"]

            # Parse and validate JSON
            try:
                response_json = json.loads(content)
                validated = response_schema(**response_json)
            except json.JSONDecodeError as e:
                raise StructuredOutputError(f"Invalid JSON from OpenRouter: {e}")
            except Exception as e:
                raise StructuredOutputError(f"Schema validation failed: {e}")

            # Calculate usage and cost
            usage = self._calculate_usage(response_data.get("usage", {}))

            return validated, usage

        except StructuredOutputError:
            raise
        except requests.exceptions.Timeout as e:
            # Week 4 Commit 21: Explicit timeout error handling
            raise LLMTimeoutError(
                f"OpenRouter request exceeded timeout of {timeout}s: {e}"
            )
        except requests.exceptions.RequestException as e:
            raise LLMError(f"OpenRouter API request failed: {e}")
        except Exception as e:
            raise LLMError(f"OpenRouter API error: {e}")

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
        # OpenRouter returns cost in USD in the usage object
        estimated_cost = float(usage_obj.get("total_cost", 0.0))

        return LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost
        )

    @property
    def model_name(self) -> str:
        """Return the OpenRouter model being used."""
        return self._model
