"""Unit tests for SQL Planner.

Week 3 Commit 17: SQL Planner

Tests the SQL planner using MockProvider to avoid real LLM API calls.
Validates:
- SQL generation from natural language
- Schema validation enforcement
- LIMIT clause requirement
- Invalid LLM output rejection
- Error handling
"""
import pytest
from pydantic import ValidationError

from enterprise_tool_router.sql_planner import SqlPlanner
from enterprise_tool_router.schemas_sql_planner import SqlPlanSchema, SqlPlanErrorSchema
from enterprise_tool_router.llm.providers import MockProvider


# Test: Basic SQL generation
def test_sql_planner_basic_generation():
    """Test basic SQL generation from natural language."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 200",
            "confidence": 0.95,
            "explanation": "Aggregates total revenue by region from sales fact table"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show me revenue by region")

    assert isinstance(result, SqlPlanSchema)
    assert "SELECT" in result.sql
    assert "LIMIT" in result.sql
    assert result.confidence == 0.95
    assert len(result.explanation) > 0


def test_sql_planner_with_limit_clause():
    """Test that SQL planner requires LIMIT clause."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 10",
            "confidence": 0.9,
            "explanation": "Select all sales records with limit"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show me sales")

    assert isinstance(result, SqlPlanSchema)
    assert "LIMIT" in result.sql.upper()


def test_sql_planner_rejects_missing_limit():
    """Test that SQL without LIMIT is rejected by schema validation."""
    # MockProvider will try to validate this, and it should fail
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact",  # Missing LIMIT
            "confidence": 0.8,
            "explanation": "Query without limit"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show me sales")

    # Should return error schema because validation failed
    assert isinstance(result, SqlPlanErrorSchema)
    assert result.confidence == 0.0
    assert "LIMIT" in result.error or "validation" in result.error.lower()


def test_sql_planner_confidence_score():
    """Test that confidence scores are validated (0.0-1.0)."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT region FROM sales_fact LIMIT 100",
            "confidence": 0.75,
            "explanation": "Simple region query"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("List regions")

    assert isinstance(result, SqlPlanSchema)
    assert 0.0 <= result.confidence <= 1.0


def test_sql_planner_invalid_confidence_score():
    """Test that invalid confidence scores are rejected."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 10",
            "confidence": 1.5,  # Invalid: > 1.0
            "explanation": "Test"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show sales")

    # Should return error because confidence validation failed
    assert isinstance(result, SqlPlanErrorSchema)
    assert result.confidence == 0.0


def test_sql_planner_missing_required_field():
    """Test that missing required fields are rejected."""
    # Missing 'explanation' field
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 10",
            "confidence": 0.9
            # 'explanation' is missing
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show sales")

    assert isinstance(result, SqlPlanErrorSchema)
    assert "validation" in result.error.lower() or "failed" in result.error.lower()


def test_sql_planner_empty_sql():
    """Test that empty SQL is rejected."""
    provider = MockProvider(
        response_data={
            "sql": "",  # Empty SQL
            "confidence": 0.5,
            "explanation": "Could not generate SQL"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Unclear query")

    assert isinstance(result, SqlPlanErrorSchema)


def test_sql_planner_empty_explanation():
    """Test that empty explanation is rejected."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 10",
            "confidence": 0.9,
            "explanation": ""  # Empty explanation
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show sales")

    assert isinstance(result, SqlPlanErrorSchema)


def test_sql_planner_schema_immutability():
    """Test that SqlPlanSchema is immutable (frozen)."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 10",
            "confidence": 0.9,
            "explanation": "Test query"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show sales")

    assert isinstance(result, SqlPlanSchema)
    # Should not be able to modify frozen schema
    with pytest.raises(Exception):  # ValidationError or AttributeError
        result.sql = "MODIFIED"


def test_sql_planner_with_complex_query():
    """Test SQL planner with a complex aggregation query."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT region, quarter, SUM(revenue) as total_revenue FROM sales_fact WHERE quarter = 'Q4' GROUP BY region, quarter ORDER BY total_revenue DESC LIMIT 50",
            "confidence": 0.88,
            "explanation": "Aggregates Q4 revenue by region, sorted by highest revenue first, limited to top 50 results"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show me top regions by Q4 revenue")

    assert isinstance(result, SqlPlanSchema)
    assert "GROUP BY" in result.sql
    assert "ORDER BY" in result.sql
    assert "LIMIT" in result.sql
    assert result.confidence == 0.88


def test_sql_planner_provider_failure():
    """Test handling of provider failures."""
    provider = MockProvider(should_fail=True)
    planner = SqlPlanner(provider)

    result = planner.plan("Any query")

    assert isinstance(result, SqlPlanErrorSchema)
    assert result.confidence == 0.0
    assert len(result.error) > 0


def test_sql_planner_model_name():
    """Test that planner exposes underlying model name."""
    provider = MockProvider()
    planner = SqlPlanner(provider)

    assert planner.model_name == "mock-llm-v1"


def test_sql_plan_schema_validator():
    """Test the LIMIT clause validator directly."""
    # Valid SQL with LIMIT
    valid_plan = SqlPlanSchema(
        sql="SELECT * FROM sales_fact LIMIT 100",
        confidence=0.9,
        explanation="Test"
    )
    assert "LIMIT" in valid_plan.sql

    # Invalid SQL without LIMIT should raise ValidationError
    with pytest.raises(ValidationError, match="LIMIT"):
        SqlPlanSchema(
            sql="SELECT * FROM sales_fact",  # No LIMIT
            confidence=0.9,
            explanation="Test"
        )


def test_sql_planner_low_confidence():
    """Test planner with low confidence score."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 200",
            "confidence": 0.4,  # Low confidence
            "explanation": "Query is ambiguous and may not match user intent"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show me stuff")

    assert isinstance(result, SqlPlanSchema)
    assert result.confidence < 0.7  # Below typical threshold


def test_sql_planner_joins():
    """Test SQL planner with JOIN query."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT sf.region, COUNT(jr.id) as job_count FROM sales_fact sf JOIN job_runs jr ON sf.region = jr.job_name LIMIT 100",
            "confidence": 0.85,
            "explanation": "Joins sales and job runs data by region"
        }
    )
    planner = SqlPlanner(provider)

    result = planner.plan("Show job counts by region")

    assert isinstance(result, SqlPlanSchema)
    assert "JOIN" in result.sql
    assert "LIMIT" in result.sql


def test_sql_error_schema():
    """Test SqlPlanErrorSchema creation."""
    error = SqlPlanErrorSchema(
        error="Test error message"
    )

    assert error.error == "Test error message"
    assert error.confidence == 0.0  # Default


def test_sql_error_schema_immutability():
    """Test that SqlPlanErrorSchema is immutable."""
    error = SqlPlanErrorSchema(error="Test")

    with pytest.raises(Exception):  # ValidationError or AttributeError
        error.error = "Modified"


# Integration-style test (still using mock)
def test_sql_planner_full_workflow():
    """Test complete workflow from natural language to validated SQL."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT quarter, AVG(revenue) as avg_revenue FROM sales_fact WHERE region = 'North America' GROUP BY quarter ORDER BY quarter LIMIT 4",
            "confidence": 0.92,
            "explanation": "Calculates average revenue per quarter for North America region, ordered chronologically"
        }
    )
    planner = SqlPlanner(provider)

    # Natural language query
    nl_query = "What is the average revenue per quarter in North America?"

    # Generate SQL plan
    plan = planner.plan(nl_query)

    # Validate result
    assert isinstance(plan, SqlPlanSchema)
    assert plan.confidence > 0.9
    assert "AVG" in plan.sql
    assert "LIMIT" in plan.sql
    assert "North America" in plan.sql
    assert len(plan.explanation) > 20  # Meaningful explanation

    # Verify schema is frozen
    assert plan.model_config.get('frozen') is True
