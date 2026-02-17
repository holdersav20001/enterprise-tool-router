"""Integration tests for Kilocode provider.

These tests verify that the Kilocode provider works correctly with the actual API.
They are skipped if KILOCODE_API_KEY is not set in the environment.
"""
import os
import pytest
from pydantic import BaseModel

from enterprise_tool_router.llm.providers import KilocodeProvider
from enterprise_tool_router.llm.base import LLMError


# Skip all tests in this file if KILOCODE_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("KILOCODE_API_KEY"),
    reason="KILOCODE_API_KEY not set - skipping Kilocode integration tests"
)


class SimpleResponse(BaseModel):
    """Simple test response schema."""
    answer: str
    confidence: float


class SqlResponse(BaseModel):
    """SQL generation response schema."""
    sql: str
    explanation: str
    confidence: float


@pytest.mark.integration
def test_kilocode_provider_basic():
    """Test basic Kilocode provider functionality."""
    provider = KilocodeProvider()

    # Simple question
    result, usage = provider.generate_structured(
        "What is 2+2? Respond with your answer and confidence (0.0-1.0).",
        SimpleResponse
    )

    # Verify response
    assert isinstance(result, SimpleResponse)
    assert isinstance(result.answer, str)
    assert 0.0 <= result.confidence <= 1.0

    # Verify usage tracking
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert usage.total_tokens == usage.input_tokens + usage.output_tokens
    assert usage.estimated_cost_usd >= 0.0


@pytest.mark.integration
def test_kilocode_provider_sql_generation():
    """Test SQL generation with Kilocode (similar to actual planner usage)."""
    provider = KilocodeProvider()

    # Natural language SQL query
    prompt = """You are a SQL query generator for a PostgreSQL database.

DATABASE SCHEMA:
1. sales_fact
   - region: varchar(50) - Geographic region
   - revenue: decimal(12,2) - Revenue in USD
   - quarter: varchar(10) - Quarter (Q1, Q2, Q3, Q4)

SAFETY RULES:
1. You MUST include a LIMIT clause
2. Only use SELECT statements

USER QUERY:
Show me revenue by region

Generate a SQL query with:
- sql: The SQL query string
- explanation: What the query does
- confidence: Your confidence score (0.0-1.0)
"""

    result, usage = provider.generate_structured(prompt, SqlResponse)

    # Verify response structure
    assert isinstance(result, SqlResponse)
    assert isinstance(result.sql, str)
    assert isinstance(result.explanation, str)
    assert 0.0 <= result.confidence <= 1.0

    # Verify SQL content
    assert "SELECT" in result.sql.upper()
    assert "revenue" in result.sql.lower()
    assert "region" in result.sql.lower()
    assert "LIMIT" in result.sql.upper()  # Safety requirement

    # Verify usage
    assert usage.total_tokens > 0


@pytest.mark.integration
def test_kilocode_provider_model_name():
    """Test that provider returns a model name."""
    provider = KilocodeProvider()

    model_name = provider.model_name
    assert isinstance(model_name, str)
    assert len(model_name) > 0


@pytest.mark.integration
def test_kilocode_provider_custom_model():
    """Test provider with custom model specification."""
    custom_model = "google/gemini-2.5-flash-preview-05-20"
    provider = KilocodeProvider(model=custom_model)

    assert provider.model_name == custom_model


@pytest.mark.integration
def test_kilocode_provider_with_explicit_key():
    """Test provider initialization with explicit API key."""
    api_key = os.getenv("KILOCODE_API_KEY")
    provider = KilocodeProvider(api_key=api_key)

    # Should work the same as with env var
    result, usage = provider.generate_structured(
        "What is 3+3?",
        SimpleResponse
    )

    assert isinstance(result, SimpleResponse)


def test_kilocode_provider_fails_without_key():
    """Test that provider raises error when API key is missing."""
    # Temporarily unset the env var for this test
    original_key = os.environ.pop("KILOCODE_API_KEY", None)

    try:
        with pytest.raises(LLMError, match="KILOCODE_API_KEY"):
            KilocodeProvider()
    finally:
        # Restore the key if it was set
        if original_key:
            os.environ["KILOCODE_API_KEY"] = original_key
