"""SQL tool with safety constraints for read-only queries.

Week 3 Update: Integrated with SQL Planner for natural language queries.

Flow:
  1. Detect if query is raw SQL or natural language
  2. If natural language: call planner → validate → execute
  3. If raw SQL: validate → execute (Week 2 behavior)
  4. Planner-generated SQL goes through same safety validator
"""
import re
from typing import Any, Optional
from decimal import Decimal

from .base import ToolResult
from ..db import get_connection
from ..schemas_sql import SqlResultSchema, SqlErrorSchema
from ..sql_planner import SqlPlanner
from ..schemas_sql_planner import SqlPlanSchema, SqlPlanErrorSchema
from ..llm.base import LLMProvider


# Week 2 allowlist: only these tables can be queried
ALLOWED_TABLES = {"sales_fact", "job_runs", "audit_log"}

# Dangerous keywords that are not allowed
BLOCKED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
    "TRUNCATE", "GRANT", "REVOKE", "COPY"
}

# Default LIMIT if not specified
DEFAULT_LIMIT = 200

# Default confidence threshold (Week 3 Commit 19)
# Queries with confidence below this threshold won't execute automatically
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


class SafetyError(Exception):
    """Raised when a query fails safety checks."""
    pass


class SqlTool:
    name = "sql"

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    ):
        """Initialize SQL tool.

        Args:
            llm_provider: Optional LLM provider for natural language queries.
                         If None, only raw SQL queries are supported.
            confidence_threshold: Minimum confidence score (0.0-1.0) required
                                 to execute LLM-generated SQL. Default: 0.7
        """
        self._llm_provider = llm_provider
        self._planner = SqlPlanner(llm_provider) if llm_provider else None
        self._confidence_threshold = confidence_threshold

    def run(self, query: str) -> ToolResult:
        """Execute a safe SQL query against Postgres.

        Week 3 Update: Supports both raw SQL and natural language queries.

        Flow:
          - If query looks like raw SQL: validate → execute (Week 2 flow)
          - If query is natural language: planner → validate → execute (Week 3 flow)

        Safety rules (applied to ALL queries, including LLM-generated):
        1. Only SELECT statements allowed
        2. No semicolons (prevents multiple statements)
        3. Block DDL/DML keywords
        4. Enforce LIMIT if absent
        5. Table allowlist check

        Returns:
            ToolResult with SqlResultSchema on success or SqlErrorSchema on failure.
        """
        try:
            # Detect if this is raw SQL or natural language
            if self._is_raw_sql(query):
                # Week 2 flow: direct validation and execution
                safe_query = self._validate_and_sanitize(query)
            else:
                # Week 3 flow: use planner, then validate
                if not self._planner:
                    raise SafetyError("Natural language queries require LLM provider")

                # Generate SQL from natural language
                plan = self._planner.plan(query)

                # Check if planner failed
                if isinstance(plan, SqlPlanErrorSchema):
                    error_schema = SqlErrorSchema(error=f"SQL generation failed: {plan.error}")
                    return ToolResult(data=error_schema.model_dump(), notes="planner_error")

                # Week 3 Commit 19: Check confidence threshold
                # If confidence is too low, don't execute - ask for clarification instead
                if plan.confidence < self._confidence_threshold:
                    clarification = SqlErrorSchema(
                        error=(
                            f"Query unclear (confidence: {plan.confidence:.2f} < {self._confidence_threshold:.2f}). "
                            f"Please rephrase or provide more specific details. "
                            f"Suggested SQL: {plan.sql}. Explanation: {plan.explanation}"
                        )
                    )
                    return ToolResult(
                        data=clarification.model_dump(),
                        notes="low_confidence"
                    )

                # Planner succeeded - now validate the generated SQL
                # This is CRITICAL: LLM output goes through same safety checks
                try:
                    safe_query = self._validate_and_sanitize(plan.sql)
                except SafetyError as e:
                    # LLM-generated SQL failed validation - reject it
                    error_schema = SqlErrorSchema(
                        error=f"Generated SQL failed safety validation: {str(e)}"
                    )
                    return ToolResult(
                        data=error_schema.model_dump(),
                        notes="planner_validation_failed"
                    )

            # Execute the validated query (from either path)
            result_schema = self._execute(safe_query)

            # Return with validated Pydantic schema (converted to dict for ToolResult)
            return ToolResult(data=result_schema.model_dump())

        except SafetyError as e:
            error_schema = SqlErrorSchema(error=str(e))
            return ToolResult(data=error_schema.model_dump(), notes="safety_violation")
        except Exception as e:
            error_schema = SqlErrorSchema(error=f"Query failed: {str(e)}")
            return ToolResult(data=error_schema.model_dump(), notes="execution_error")

    def _is_raw_sql(self, query: str) -> bool:
        """Detect if query is raw SQL or natural language.

        Heuristic:
        - If starts with common SQL keywords, treat as raw SQL
        - This includes both valid (SELECT) and invalid (DROP, INSERT, etc.) SQL
        - Otherwise, treat as natural language

        Args:
            query: Input query string

        Returns:
            True if raw SQL, False if natural language
        """
        normalized = query.strip().upper()

        # Common SQL statement keywords (both valid and invalid)
        sql_keywords = [
            "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
            "ALTER", "TRUNCATE", "GRANT", "REVOKE", "WITH", "COPY"
        ]

        for keyword in sql_keywords:
            if normalized.startswith(keyword):
                return True

        return False

    def _validate_and_sanitize(self, query: str) -> str:
        """Validate and sanitize the query.

        Raises:
            SafetyError: If query violates safety rules.

        Returns:
            Sanitized query with LIMIT enforced if needed.
        """
        normalized = query.strip()
        upper = normalized.upper()

        # Rule 1: Must start with SELECT
        if not upper.startswith("SELECT"):
            raise SafetyError("Only SELECT statements are allowed")

        # Rule 2: No semicolons (prevents multiple statements)
        if ";" in normalized:
            raise SafetyError("Semicolons are not allowed")

        # Rule 3: Block dangerous keywords
        for keyword in BLOCKED_KEYWORDS:
            # Use word boundary check
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, upper):
                raise SafetyError(f"Keyword '{keyword}' is not allowed")

        # Rule 5: Check table allowlist
        # Extract potential table names (simplified regex-based approach)
        # Look for FROM and JOIN clauses
        from_pattern = r'\bFROM\s+(\w+)'
        join_pattern = r'\bJOIN\s+(\w+)'

        tables_found = set()
        for match in re.finditer(from_pattern, upper):
            tables_found.add(match.group(1).lower())
        for match in re.finditer(join_pattern, upper):
            tables_found.add(match.group(1).lower())

        for table in tables_found:
            if table not in ALLOWED_TABLES:
                raise SafetyError(f"Table '{table}' is not in the allowlist")

        # Rule 4: Enforce LIMIT if absent
        # Check if LIMIT already exists
        if not re.search(r'\bLIMIT\s+\d+', upper):
            normalized = f"{normalized} LIMIT {DEFAULT_LIMIT}"

        return normalized

    def _execute(self, query: str) -> SqlResultSchema:
        """Execute the validated query against the database.

        Returns:
            SqlResultSchema with validated, serializable data.
            No raw database driver objects (e.g., Decimal) are leaked.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)

                # Get column names
                columns = [desc[0] for desc in cur.description] if cur.description else []

                # Fetch all rows and convert to serializable types
                rows = cur.fetchall()
                serialized_rows = []
                for row in rows:
                    serialized_row = []
                    for value in row:
                        # Convert Decimal to float for JSON serialization
                        if isinstance(value, Decimal):
                            serialized_row.append(float(value))
                        else:
                            serialized_row.append(value)
                    serialized_rows.append(serialized_row)

                # Return validated Pydantic schema
                return SqlResultSchema(
                    columns=columns,
                    rows=serialized_rows,
                    row_count=len(serialized_rows)
                )
