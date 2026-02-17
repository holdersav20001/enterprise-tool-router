"""Integration tests for SQL Planner + Validator.

Week 3 Commit 18: Integrate Planner + Validator

Tests the complete flow:
  Natural Language → Planner → Validator → Execution

Critical test cases:
1. NL query generates SQL and executes successfully
2. Malicious planner output is blocked by validator
3. Raw SQL bypass still works (backward compatibility)
4. Planner errors are handled gracefully
5. Validation failures for LLM-generated SQL
"""
import pytest

from enterprise_tool_router.tools.sql import SqlTool
from enterprise_tool_router.llm.providers import MockProvider
from enterprise_tool_router.schemas_sql import SqlResultSchema, SqlErrorSchema


# Test: Natural language query → planner → validator → execution
def test_natural_language_query_success():
    """Test complete flow: NL query → SQL generation → validation → execution."""
    # Mock LLM that generates valid SQL
    provider = MockProvider(
        response_data={
            "sql": "SELECT region, revenue FROM sales_fact WHERE quarter = 'Q4' LIMIT 10",
            "confidence": 0.92,
            "explanation": "Filters Q4 sales by region"
        }
    )
    tool = SqlTool(llm_provider=provider)

    # Natural language query (doesn't start with SELECT)
    result = tool.run("Show me Q4 revenue by region")

    # Should succeed - planner generates SQL, validator approves, DB executes
    assert "error" not in result.data
    # Result should have SQL result structure
    if "columns" in result.data:
        assert isinstance(result.data.get("columns"), list)


def test_malicious_planner_output_blocked():
    """Test that malicious LLM output is blocked by validator.

    CRITICAL: Even if LLM tries to generate malicious SQL,
    the deterministic validator must reject it.
    """
    # Mock LLM that tries to generate SQL with semicolon (multi-statement attack)
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact; DROP TABLE audit_log LIMIT 10",
            "confidence": 0.95,
            "explanation": "Malicious attempt"
        }
    )
    tool = SqlTool(llm_provider=provider)

    # Natural language query (doesn't start with SQL keyword)
    result = tool.run("Show me sales and delete audit log")

    # Should be rejected by validator
    assert "error" in result.data
    assert result.notes == "planner_validation_failed"
    assert "safety validation" in result.data["error"].lower()


def test_malicious_planner_insert_blocked():
    """Test that INSERT statements from LLM are blocked."""
    provider = MockProvider(
        response_data={
            "sql": "INSERT INTO sales_fact (region, revenue) VALUES ('Fake', 99999) LIMIT 1",
            "confidence": 0.9,
            "explanation": "Trying to insert data"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Add fake sales data")

    assert "error" in result.data
    assert result.notes == "planner_validation_failed"


def test_malicious_planner_no_limit():
    """Test that SQL without LIMIT from LLM is blocked.

    Note: The planner's schema validator should catch this first,
    but if it somehow gets through, the SQL validator will catch it.
    """
    # This should fail at planner schema validation
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact",  # No LIMIT
            "confidence": 0.8,
            "explanation": "Missing limit"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show all sales")

    # Should fail (either at planner schema or validator)
    assert "error" in result.data


def test_raw_sql_bypass_still_works():
    """Test backward compatibility: raw SQL queries still work without planner.

    CRITICAL: Existing raw SQL queries must continue to work.
    """
    # No LLM provider needed for raw SQL
    tool = SqlTool()

    # Raw SQL query (starts with SELECT)
    result = tool.run("SELECT region FROM sales_fact LIMIT 5")

    # Should execute directly without planner
    assert "error" not in result.data or result.data.get("row_count") is not None


def test_raw_sql_with_llm_provider():
    """Test that raw SQL works even when LLM provider is available."""
    provider = MockProvider(
        response_data={"sql": "unused", "confidence": 0.5, "explanation": "unused"}
    )
    tool = SqlTool(llm_provider=provider)

    # Raw SQL should bypass planner
    result = tool.run("SELECT * FROM job_runs LIMIT 3")

    # Should succeed without using planner
    assert "error" not in result.data or result.data.get("row_count") is not None


def test_natural_language_without_llm_fails():
    """Test that NL queries fail gracefully when no LLM provider is configured."""
    tool = SqlTool()  # No LLM provider

    # Natural language query
    result = tool.run("Show me recent sales")

    # Should fail with clear error
    assert "error" in result.data
    assert "LLM provider" in result.data["error"] or "natural language" in result.data["error"].lower()


def test_planner_error_handled(clean_query_history):
    """Test that planner errors are handled gracefully."""
    # Mock provider configured to fail
    provider = MockProvider(should_fail=True)
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me sales data", bypass_cache=True)

    # Should return error schema
    assert "error" in result.data
    assert result.notes == "planner_error"


def test_planner_low_confidence_blocked():
    """Test that low-confidence queries don't execute (Commit 19).

    As of Commit 19, low-confidence queries are blocked to prevent
    speculative execution of uncertain queries.
    """
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact LIMIT 50",
            "confidence": 0.3,  # Low confidence (< 0.7 threshold)
            "explanation": "Uncertain query"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me stuff")

    # Commit 19: Low confidence queries are now blocked
    assert result.notes == "low_confidence"
    assert "error" in result.data
    assert "confidence" in result.data["error"].lower()


def test_planner_table_allowlist_enforced():
    """Test that planner-generated SQL with disallowed tables is blocked."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM users LIMIT 10",  # 'users' not in allowlist
            "confidence": 0.9,
            "explanation": "Query disallowed table"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me user data")

    # Should be blocked by validator
    assert "error" in result.data
    assert result.notes == "planner_validation_failed"
    assert "allowlist" in result.data["error"].lower() or "users" in result.data["error"]


def test_is_raw_sql_detection():
    """Test the raw SQL detection heuristic."""
    tool = SqlTool()

    # These should be detected as raw SQL (valid)
    assert tool._is_raw_sql("SELECT * FROM sales_fact")
    assert tool._is_raw_sql("  SELECT region FROM job_runs  ")
    assert tool._is_raw_sql("select * from audit_log")  # lowercase

    # These should also be detected as raw SQL (invalid but still SQL keywords)
    assert tool._is_raw_sql("DROP TABLE sales_fact")
    assert tool._is_raw_sql("INSERT INTO sales_fact VALUES (1, 2)")
    assert tool._is_raw_sql("UPDATE sales_fact SET revenue = 0")
    assert tool._is_raw_sql("DELETE FROM sales_fact")

    # These should be detected as natural language
    assert not tool._is_raw_sql("Show me sales data")
    assert not tool._is_raw_sql("What is the revenue by region?")
    assert not tool._is_raw_sql("List all job runs")
    assert not tool._is_raw_sql("")


def test_planner_semicolon_blocked():
    """Test that planner-generated SQL with semicolons is blocked."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT * FROM sales_fact; DROP TABLE audit_log LIMIT 10",
            "confidence": 0.9,
            "explanation": "SQL injection attempt"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show sales and delete audit log")

    # Should be blocked by validator (semicolon rule)
    assert "error" in result.data
    assert result.notes == "planner_validation_failed"


def test_planner_complex_valid_query():
    """Test that complex but valid planner-generated SQL passes validation."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT region, quarter, SUM(revenue) as total FROM sales_fact WHERE quarter IN ('Q3', 'Q4') GROUP BY region, quarter ORDER BY total DESC LIMIT 20",
            "confidence": 0.95,
            "explanation": "Aggregates Q3/Q4 revenue by region and quarter"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show me total revenue by region for Q3 and Q4")

    # Complex but safe SQL should pass validation
    assert "error" not in result.data or result.data.get("row_count") is not None


def test_raw_sql_safety_still_enforced():
    """Test that raw SQL queries still go through safety validation."""
    tool = SqlTool()

    # Try raw SQL with blocked keyword
    result = tool.run("SELECT * FROM sales_fact; DROP TABLE job_runs")

    # Should be blocked by validator
    assert "error" in result.data
    assert result.notes == "safety_violation"


def test_planner_generated_sql_gets_limit_added():
    """Test that if planner somehow generates SQL without LIMIT, it gets rejected.

    The planner schema should enforce LIMIT, but if it gets through,
    the validator will add it.
    """
    # This would fail at planner schema validation in practice
    # but testing the validator's LIMIT enforcement
    provider = MockProvider(
        response_data={
            "sql": "SELECT region FROM sales_fact",  # Will fail schema validation
            "confidence": 0.8,
            "explanation": "Test"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show regions")

    # Should fail due to missing LIMIT
    assert "error" in result.data


# Edge cases
def test_empty_query():
    """Test handling of empty query."""
    tool = SqlTool()
    result = tool.run("")

    # Should fail (not raw SQL, no planner)
    assert "error" in result.data


def test_whitespace_query():
    """Test handling of whitespace-only query."""
    tool = SqlTool()
    result = tool.run("   ")

    # Should fail
    assert "error" in result.data


def test_planner_with_joins():
    """Test planner-generated SQL with JOINs passes validation."""
    provider = MockProvider(
        response_data={
            "sql": "SELECT sf.region, COUNT(jr.id) FROM sales_fact sf JOIN job_runs jr ON sf.region = jr.job_name GROUP BY sf.region LIMIT 50",
            "confidence": 0.88,
            "explanation": "Joins sales and jobs"
        }
    )
    tool = SqlTool(llm_provider=provider)

    result = tool.run("Show job counts by sales region")

    # JOIN with allowed tables should pass
    assert "error" not in result.data or result.data.get("row_count") is not None
