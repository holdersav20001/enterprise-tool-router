"""Unit tests for confidence threshold enforcement.

Week 3 Commit 19: Confidence Threshold

Tests that low-confidence queries don't execute automatically and
high-confidence queries proceed normally.

Critical Safety Property:
If the LLM is uncertain about the query (low confidence), the system
should NOT execute speculatively. Instead, it should ask for clarification.
"""
import pytest

from enterprise_tool_router.tools.sql import SqlTool, DEFAULT_CONFIDENCE_THRESHOLD
from enterprise_tool_router.llm.providers import MockProvider


def test_low_confidence_query_blocked():
    """Test that low-confidence queries don't execute."""
    # Mock LLM with low confidence (< 0.7)
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.5,  # Below default threshold
            "explanation": "Unclear what data is needed"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me some data")

    # Should NOT execute
    assert "error" in result.data
    assert result.notes == "low_confidence"
    assert "confidence" in result.data["error"].lower()
    assert "0.50" in result.data["error"]  # Shows actual confidence
    assert "0.70" in result.data["error"]  # Shows threshold


def test_high_confidence_query_executes():
    """Test that high-confidence queries execute normally."""
    # Mock LLM with high confidence (>= 0.7)
    provider = MockProvider(
        response_data={
            "sql": "SELECT region, revenue FROM sales_fact LIMIT 50",
            "confidence": 0.95,  # Above threshold
            "explanation": "Clear query for region revenue"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me revenue by region")

    # Should execute successfully
    # May return error from DB (no connection in unit test) but should pass confidence check
    assert result.notes != "low_confidence"


def test_confidence_at_threshold_executes():
    """Test that confidence exactly at threshold (0.7) executes."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.7,  # Exactly at threshold
            "explanation": "Borderline query"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show sales")

    # Should execute (>= threshold, not >)
    assert result.notes != "low_confidence"


def test_confidence_just_below_threshold_blocked():
    """Test that confidence just below threshold is blocked."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.69,  # Just below 0.7
            "explanation": "Slightly unclear"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me stuff")

    # Should be blocked
    assert result.notes == "low_confidence"


def test_custom_confidence_threshold():
    """Test using a custom confidence threshold."""
    # Mock LLM with confidence 0.6
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.6,
            "explanation": "Medium confidence"
        }
    )

    # Default threshold (0.7) - should block
    tool_default = SqlTool(llm_provider=provider)
    result_default = tool_default.run("Show sales")
    assert result_default.notes == "low_confidence"

    # Custom threshold (0.5) - should execute
    tool_custom = SqlTool(llm_provider=provider, confidence_threshold=0.5)
    result_custom = tool_custom.run("Show sales")
    assert result_custom.notes != "low_confidence"


def test_very_low_confidence_blocked():
    """Test that very low confidence (e.g., 0.1) is blocked."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.1,  # Very low
            "explanation": "Completely unclear query"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("What?")

    assert result.notes == "low_confidence"


def test_confidence_threshold_includes_suggested_sql():
    """Test that low-confidence response includes suggested SQL for user review."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 200",
            "confidence": 0.6,
            "explanation": "Guessing at revenue aggregation"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me something about revenue")

    # Should include the suggested SQL in the clarification message
    assert result.notes == "low_confidence"
    assert "SELECT region" in result.data["error"]
    assert "Guessing at revenue aggregation" in result.data["error"]


def test_confidence_threshold_zero_allows_all():
    """Test that threshold of 0.0 allows all queries."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.01,  # Very low
            "explanation": "Test"
        }
    )
    tool = SqlTool(llm_provider=provider, confidence_threshold=0.0)

    result = tool.run("Random query")

    # Should not be blocked by confidence
    assert result.notes != "low_confidence"


def test_confidence_threshold_one_blocks_all():
    """Test that threshold of 1.0 blocks everything except perfect confidence."""
    # Confidence 0.99 (high but not perfect)
    provider_high = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.99,
            "explanation": "Test"
        }
    )
    tool = SqlTool(llm_provider=provider_high, confidence_threshold=1.0)
    result = tool.run("Show sales")
    assert result.notes == "low_confidence"

    # Confidence 1.0 (perfect)
    provider_perfect = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 1.0,
            "explanation": "Test"
        }
    )
    tool_perfect = SqlTool(llm_provider=provider_perfect, confidence_threshold=1.0)
    result_perfect = tool_perfect.run("Show sales")
    assert result_perfect.notes != "low_confidence"


def test_raw_sql_bypasses_confidence_check():
    """Test that raw SQL queries bypass confidence checking."""
    # Even with high threshold, raw SQL should work
    tool = SqlTool(confidence_threshold=1.0)

    # Raw SQL (starts with SELECT)
    result = tool.run("SELECT * FROM sales_fact LIMIT 10")

    # Should not be blocked by confidence (no planner used)
    assert result.notes != "low_confidence"


def test_confidence_with_validation_failure():
    """Test that confidence check happens BEFORE validation.

    If query passes confidence but generated SQL fails validation,
    it should be rejected with planner_validation_failed.
    """
    # High confidence but invalid SQL (has semicolon)
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact; DROP TABLE audit_log LIMIT 10",  # Invalid (semicolon)
            "confidence": 0.95,  # High confidence
            "explanation": "Malicious SQL with SQL injection"
        }
    )
    tool = SqlTool(llm_provider=provider)

    # Natural language query (not raw SQL)
    result = tool.run("Show me sales and delete audit log")

    # Should fail at validation, not confidence
    assert result.notes == "planner_validation_failed"
    assert result.notes != "low_confidence"


def test_low_confidence_with_invalid_sql():
    """Test that low confidence is checked before validation.

    If both confidence is low AND SQL is invalid, confidence check
    should happen first (fail fast).
    """
    # Low confidence AND invalid SQL (has semicolon)
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact; DROP TABLE audit_log LIMIT 10",  # Invalid
            "confidence": 0.3,  # Low confidence
            "explanation": "Unclear and dangerous"
        }
    )
    tool = SqlTool(llm_provider=provider)

    # Natural language query
    result = tool.run("Do something with sales")

    # Should fail at confidence check BEFORE reaching validator
    assert result.notes == "low_confidence"


def test_default_threshold_value():
    """Test that default threshold is 0.7."""
    assert DEFAULT_CONFIDENCE_THRESHOLD == 0.7


def test_confidence_threshold_in_range():
    """Test confidence threshold validation (should be 0.0-1.0)."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.8,
            "explanation": "Test"
        }
    )

    # Valid thresholds
    tool_valid = SqlTool(llm_provider=provider, confidence_threshold=0.5)
    assert tool_valid._confidence_threshold == 0.5

    # Edge cases
    tool_zero = SqlTool(llm_provider=provider, confidence_threshold=0.0)
    assert tool_zero._confidence_threshold == 0.0

    tool_one = SqlTool(llm_provider=provider, confidence_threshold=1.0)
    assert tool_one._confidence_threshold == 1.0


def test_multiple_queries_with_different_confidence():
    """Test that the same tool handles multiple queries with varying confidence."""
    tool = SqlTool(
        llm_provider=MockProvider(
            response_data={
                "sql": "SELECT * FROM sales_fact LIMIT 100",
                "confidence": 0.5,  # Will change per test
                "explanation": "Test"
            }
        )
    )

    # Low confidence query
    provider_low = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.5,
            "explanation": "Unclear"
        }
    )
    tool_low = SqlTool(llm_provider=provider_low)
    result_low = tool_low.run("Show me data")
    assert result_low.notes == "low_confidence"

    # High confidence query
    provider_high = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 100",
            "confidence": 0.95,
            "explanation": "Clear"
        }
    )
    tool_high = SqlTool(llm_provider=provider_high)
    result_high = tool_high.run("Show me sales data")
    assert result_high.notes != "low_confidence"
