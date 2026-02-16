"""Unit tests for LLM abstraction layer.

Week 3 Commit 16: LLM Abstraction Layer

Tests the provider interface using MockProvider to avoid real API calls.
Validates:
- Structured output generation and validation
- Token usage tracking
- Error handling
- Schema compliance
"""
import pytest
from pydantic import BaseModel, Field, ConfigDict

from enterprise_tool_router.llm import LLMProvider, LLMUsage, LLMError, StructuredOutputError
from enterprise_tool_router.llm.providers import MockProvider


# Test schemas
class SqlPlanSchema(BaseModel):
    """Example schema for SQL planning."""
    sql: str = Field(..., description="Generated SQL query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    explanation: str = Field(..., description="Explanation of the SQL")

    model_config = ConfigDict(frozen=True)


class SimpleSchema(BaseModel):
    """Simple schema for basic testing."""
    message: str


# Test: MockProvider basic functionality
def test_mock_provider_basic():
    """Test basic MockProvider structured output generation."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 200",
            "confidence": 0.95,
            "explanation": "Simple select query with safety limit"
        }
    )

    result, usage = provider.generate_structured(
        "Show me all sales",
        SqlPlanSchema
    )

    # Validate response
    assert isinstance(result, SqlPlanSchema)
    assert result.sql == "SELECT * FROM sales_fact LIMIT 200"
    assert result.confidence == 0.95
    assert result.explanation == "Simple select query with safety limit"

    # Validate usage
    assert isinstance(usage, LLMUsage)
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.total_tokens == 150
    assert usage.estimated_cost_usd > 0


def test_mock_provider_schema_validation():
    """Test that MockProvider validates against Pydantic schema."""
    provider = MockProvider(
        response_data={
            "message": "Hello, World!"
        }
    )

    result, usage = provider.generate_structured(
        "Say hello",
        SimpleSchema
    )

    assert isinstance(result, SimpleSchema)
    assert result.message == "Hello, World!"


def test_mock_provider_invalid_schema():
    """Test that invalid data raises StructuredOutputError."""
    # Missing required field 'confidence'
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact",
            "explanation": "Missing confidence field"
        }
    )

    with pytest.raises(StructuredOutputError, match="Mock data validation failed"):
        provider.generate_structured(
            "Show me sales",
            SqlPlanSchema
        )


def test_mock_provider_configured_failure():
    """Test that MockProvider can be configured to fail."""
    provider = MockProvider(should_fail=True)

    with pytest.raises(StructuredOutputError, match="Mock provider configured to fail"):
        provider.generate_structured(
            "Any prompt",
            SimpleSchema
        )


def test_mock_provider_schema_constraint_validation():
    """Test that Pydantic constraints are enforced."""
    # Confidence out of range
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact",
            "confidence": 1.5,  # Invalid: must be <= 1.0
            "explanation": "Test"
        }
    )

    with pytest.raises(StructuredOutputError):
        provider.generate_structured(
            "Show me sales",
            SqlPlanSchema
        )


def test_mock_provider_model_name():
    """Test that MockProvider returns model name."""
    provider = MockProvider()
    assert provider.model_name == "mock-llm-v1"


def test_llm_usage_immutability():
    """Test that LLMUsage is immutable (frozen dataclass)."""
    usage = LLMUsage(
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.001
    )

    # Should not be able to modify
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        usage.input_tokens = 200


def test_mock_provider_custom_tokens():
    """Test MockProvider with custom token counts."""
    provider = MockProvider(
        response_data={"message": "test"},
        input_tokens=500,
        output_tokens=250
    )

    result, usage = provider.generate_structured(
        "prompt",
        SimpleSchema
    )

    assert usage.input_tokens == 500
    assert usage.output_tokens == 250
    assert usage.total_tokens == 750


def test_schema_frozen():
    """Test that response schemas are immutable when frozen."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact",
            "confidence": 0.8,
            "explanation": "Test query"
        }
    )

    result, usage = provider.generate_structured(
        "prompt",
        SqlPlanSchema
    )

    # SqlPlanSchema is frozen, should not be modifiable
    with pytest.raises(Exception):  # ValidationError
        result.sql = "MODIFIED"


def test_provider_interface_contract():
    """Test that MockProvider implements LLMProvider interface."""
    provider = MockProvider()

    # Check that it has the required interface
    assert hasattr(provider, 'generate_structured')
    assert hasattr(provider, 'model_name')
    assert callable(provider.generate_structured)
    assert isinstance(provider.model_name, str)


def test_empty_response_data():
    """Test MockProvider with empty response data."""
    # SimpleSchema requires 'message' field
    provider = MockProvider(response_data={})

    with pytest.raises(StructuredOutputError):
        provider.generate_structured(
            "prompt",
            SimpleSchema
        )


# Integration tests would go here for real providers
# These would require API keys and would be marked with @pytest.mark.integration
# Example:
#
# @pytest.mark.integration
# def test_anthropic_provider_real_call():
#     """Integration test for AnthropicProvider (requires API key)."""
#     import os
#     if not os.getenv("ANTHROPIC_API_KEY"):
#         pytest.skip("ANTHROPIC_API_KEY not set")
#
#     provider = AnthropicProvider()
#     result, usage = provider.generate_structured(
#         "What is 2+2? Answer in JSON with field 'answer'",
#         SimpleSchema
#     )
#     assert isinstance(result, SimpleSchema)
#     assert usage.total_tokens > 0
