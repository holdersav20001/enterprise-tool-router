"""SQL tool with safety constraints for read-only queries."""
import re
from typing import Any
from decimal import Decimal

from .base import ToolResult
from ..db import get_connection
from ..schemas_sql import SqlResultSchema, SqlErrorSchema


# Week 2 allowlist: only these tables can be queried
ALLOWED_TABLES = {"sales_fact", "job_runs", "audit_log"}

# Dangerous keywords that are not allowed
BLOCKED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
    "TRUNCATE", "GRANT", "REVOKE", "COPY"
}

# Default LIMIT if not specified
DEFAULT_LIMIT = 200


class SafetyError(Exception):
    """Raised when a query fails safety checks."""
    pass


class SqlTool:
    name = "sql"

    def run(self, query: str) -> ToolResult:
        """Execute a safe SQL query against Postgres.

        Safety rules:
        1. Only SELECT statements allowed
        2. No semicolons (prevents multiple statements)
        3. Block DDL/DML keywords
        4. Enforce LIMIT if absent
        5. Table allowlist check

        Returns:
            ToolResult with SqlResultSchema on success or SqlErrorSchema on failure.
        """
        try:
            # Run safety checks
            safe_query = self._validate_and_sanitize(query)

            # Execute query
            result_schema = self._execute(safe_query)

            # Return with validated Pydantic schema (converted to dict for ToolResult)
            return ToolResult(data=result_schema.model_dump())

        except SafetyError as e:
            error_schema = SqlErrorSchema(error=str(e))
            return ToolResult(data=error_schema.model_dump(), notes="safety_violation")
        except Exception as e:
            error_schema = SqlErrorSchema(error=f"Query failed: {str(e)}")
            return ToolResult(data=error_schema.model_dump(), notes="execution_error")

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
