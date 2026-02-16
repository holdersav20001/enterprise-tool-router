"""Tests for SQL tool safety features."""
import pytest
from decimal import Decimal

from enterprise_tool_router.tools.sql import SqlTool, SafetyError, BLOCKED_KEYWORDS, DEFAULT_LIMIT
from enterprise_tool_router.schemas_sql import SqlResultSchema, SqlErrorSchema


class TestSqlSafety:
    """Test SQL safety validation without database connection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SqlTool()

    def test_select_only_allowed(self):
        """Only SELECT statements are allowed."""
        # Valid SELECT
        result = self.tool._validate_and_sanitize("SELECT * FROM sales_fact")
        assert result.startswith("SELECT")

        # INSERT blocked
        with pytest.raises(SafetyError, match="Only SELECT"):
            self.tool._validate_and_sanitize("INSERT INTO sales_fact VALUES (1)")

        # UPDATE blocked
        with pytest.raises(SafetyError, match="Only SELECT"):
            self.tool._validate_and_sanitize("UPDATE sales_fact SET revenue = 100")

        # DELETE blocked
        with pytest.raises(SafetyError, match="Only SELECT"):
            self.tool._validate_and_sanitize("DELETE FROM sales_fact")

    def test_no_semicolons(self):
        """Semicolons are not allowed (prevents multiple statements)."""
        with pytest.raises(SafetyError, match="Semicolons"):
            self.tool._validate_and_sanitize("SELECT * FROM sales_fact; DROP TABLE sales_fact")

        with pytest.raises(SafetyError, match="Semicolons"):
            self.tool._validate_and_sanitize("SELECT * FROM sales_fact;")

    def test_blocked_keywords(self):
        """DDL/DML keywords are blocked."""
        for keyword in BLOCKED_KEYWORDS:
            # Test keyword in various positions
            query = f"SELECT * FROM sales_fact WHERE name = '{keyword}'"
            # This should pass (keyword in string literal context)

            # Test keyword as actual command
            query = f"SELECT * FROM sales_fact {keyword}"
            with pytest.raises(SafetyError, match=keyword):
                self.tool._validate_and_sanitize(query)

    def test_create_blocked(self):
        """CREATE is blocked by SELECT-only rule."""
        with pytest.raises(SafetyError, match="Only SELECT"):
            self.tool._validate_and_sanitize("CREATE TABLE test (id INT)")

    def test_drop_blocked(self):
        """DROP is blocked by SELECT-only rule."""
        with pytest.raises(SafetyError, match="Only SELECT"):
            self.tool._validate_and_sanitize("DROP TABLE sales_fact")

    def test_alter_blocked(self):
        """ALTER is blocked by SELECT-only rule."""
        with pytest.raises(SafetyError, match="Only SELECT"):
            self.tool._validate_and_sanitize("ALTER TABLE sales_fact ADD COLUMN x INT")

    def test_limit_enforced_when_missing(self):
        """LIMIT is added if not present."""
        query = "SELECT * FROM sales_fact"
        result = self.tool._validate_and_sanitize(query)
        assert f"LIMIT {DEFAULT_LIMIT}" in result

    def test_limit_preserved_when_present(self):
        """Existing LIMIT is preserved."""
        query = "SELECT * FROM sales_fact LIMIT 50"
        result = self.tool._validate_and_sanitize(query)
        assert "LIMIT 50" in result
        assert f"LIMIT {DEFAULT_LIMIT}" not in result

    def test_table_allowlist_allowed_tables(self):
        """Queries on allowlisted tables are allowed."""
        for table in ["sales_fact", "job_runs", "audit_log"]:
            query = f"SELECT * FROM {table}"
            result = self.tool._validate_and_sanitize(query)
            assert table in result

    def test_table_allowlist_blocked_tables(self):
        """Queries on non-allowlisted tables are blocked."""
        with pytest.raises(SafetyError, match="not in the allowlist"):
            self.tool._validate_and_sanitize("SELECT * FROM users")

        with pytest.raises(SafetyError, match="not in the allowlist"):
            self.tool._validate_and_sanitize("SELECT * FROM pg_admin")

    def test_join_with_allowed_tables(self):
        """JOINs between allowed tables are permitted."""
        query = """
            SELECT s.region, j.job_name
            FROM sales_fact s
            JOIN job_runs j ON s.id = j.id
        """
        result = self.tool._validate_and_sanitize(query)
        assert "sales_fact" in result
        assert "job_runs" in result


class TestSqlToolIntegration:
    """Integration tests requiring database connection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SqlTool()

    def test_run_returns_valid_result(self):
        """Query execution returns structured result."""
        result = self.tool.run("SELECT region, quarter FROM sales_fact LIMIT 3")

        # Should not have error
        assert "error" not in result.data

        # Should have expected structure
        assert "columns" in result.data
        assert "rows" in result.data
        assert "row_count" in result.data

        # Verify structure
        assert result.data["columns"] == ["region", "quarter"]
        assert result.data["row_count"] == 3
        assert len(result.data["rows"]) == 3

    def test_run_with_safety_violation(self):
        """Safety violations return error in result."""
        result = self.tool.run("DROP TABLE sales_fact")

        assert "error" in result.data
        assert result.notes == "safety_violation"

    def test_run_enforces_default_limit(self):
        """Default LIMIT is enforced on queries."""
        # Query without limit should get default
        result = self.tool.run("SELECT id FROM sales_fact")

        # sales_fact has 16 rows, but default limit is 200
        assert result.data["row_count"] == 16  # All rows since 16 < 200

    def test_run_respects_explicit_limit(self):
        """Explicit LIMIT is respected."""
        result = self.tool.run("SELECT id FROM sales_fact LIMIT 5")

        assert result.data["row_count"] == 5


class TestSqlSchemas:
    """Test Pydantic schema validation for SQL tool output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = SqlTool()

    def test_success_result_validates_against_schema(self):
        """Successful query results validate against SqlResultSchema."""
        result = self.tool.run("SELECT region, revenue FROM sales_fact LIMIT 2")

        # Should not have error
        assert "error" not in result.data

        # Data should validate against SqlResultSchema
        schema = SqlResultSchema(**result.data)
        assert schema.columns == ["region", "revenue"]
        assert schema.row_count == 2
        assert len(schema.rows) == 2
        assert len(schema.rows[0]) == 2  # Two columns per row

    def test_error_result_validates_against_error_schema(self):
        """Error results validate against SqlErrorSchema."""
        result = self.tool.run("DROP TABLE sales_fact")

        # Should have error
        assert "error" in result.data
        assert result.notes == "safety_violation"

        # Data should validate against SqlErrorSchema
        schema = SqlErrorSchema(**result.data)
        assert "Only SELECT" in schema.error

    def test_no_raw_decimal_objects_in_output(self):
        """Ensure Decimal objects are converted to float for JSON serialization."""
        result = self.tool.run("SELECT revenue FROM sales_fact LIMIT 1")

        # Get the first revenue value
        revenue_value = result.data["rows"][0][0]

        # Should be float, not Decimal (Decimal breaks JSON serialization)
        assert isinstance(revenue_value, float), f"Expected float, got {type(revenue_value)}"
        assert not isinstance(revenue_value, Decimal), "Decimal objects must be converted to float"

    def test_schema_is_stable_and_complete(self):
        """Output schema has all required fields with correct types."""
        result = self.tool.run("SELECT id, region FROM sales_fact LIMIT 1")

        # Validate schema structure
        schema = SqlResultSchema(**result.data)

        # Check types
        assert isinstance(schema.columns, list)
        assert all(isinstance(col, str) for col in schema.columns)
        assert isinstance(schema.rows, list)
        assert all(isinstance(row, list) for row in schema.rows)
        assert isinstance(schema.row_count, int)

        # Check immutability (frozen=True in schema)
        with pytest.raises(Exception):  # Pydantic ValidationError or AttributeError
            schema.row_count = 999

    def test_empty_result_validates(self):
        """Empty query results still validate against schema."""
        result = self.tool.run("SELECT * FROM sales_fact WHERE 1=0 LIMIT 10")

        # Should return empty but valid schema
        schema = SqlResultSchema(**result.data)
        assert schema.row_count == 0
        assert schema.rows == []
        assert len(schema.columns) > 0  # Columns still present even with no rows
