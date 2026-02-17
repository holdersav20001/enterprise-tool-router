"""Audit logging for query operations (append-only)."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from contextlib import contextmanager
import time

from .db import get_connection


def hash_data(data: Any) -> str:
    """Generate SHA256 hash of data for audit trail.

    Args:
        data: Any JSON-serializable data (dict, list, str, etc.)

    Returns:
        Hexadecimal SHA256 hash string.
    """
    # Convert to JSON string with sorted keys for deterministic hashing
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


def log_audit_record(
    correlation_id: str,
    tool: str,
    action: str,
    input_data: Any,
    output_data: Any,
    success: bool,
    duration_ms: int,
    user_id: Optional[str] = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_usd: float = 0.0
) -> None:
    """Write an audit record to the audit_log table (append-only).

    Args:
        correlation_id: Unique request identifier for tracing.
        tool: Tool name (sql, vector, rest, etc.).
        action: Action performed (query, insert, etc.).
        input_data: Input data to hash.
        output_data: Output data to hash.
        success: Whether the operation succeeded.
        duration_ms: Operation duration in milliseconds.
        user_id: Optional user identifier.
        tokens_input: Number of input tokens (LLM) - Week 4 Commit 26
        tokens_output: Number of output tokens (LLM) - Week 4 Commit 26
        cost_usd: Estimated cost in USD - Week 4 Commit 26

    Raises:
        Exception: If database insert fails.
    """
    # Generate hashes
    input_hash = hash_data(input_data)
    output_hash = hash_data(output_data)

    # Insert audit record (append-only)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (
                    ts, correlation_id, user_id, tool, action,
                    input_hash, output_hash, success, duration_ms,
                    tokens_input, tokens_output, cost_usd
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    datetime.now(timezone.utc),
                    correlation_id,
                    user_id,
                    tool,
                    action,
                    input_hash,
                    output_hash,
                    success,
                    duration_ms,
                    tokens_input,
                    tokens_output,
                    cost_usd
                )
            )
            conn.commit()


@contextmanager
def audit_context(
    correlation_id: str,
    tool: str,
    action: str,
    input_data: Any,
    user_id: Optional[str] = None
):
    """Context manager for auditing operations with automatic timing.

    Usage:
        with audit_context("trace-123", "sql", "query", {"query": "SELECT..."}) as ctx:
            result = execute_query(...)
            ctx.set_output(result)

    Args:
        correlation_id: Unique request identifier.
        tool: Tool name.
        action: Action being performed.
        input_data: Input data to audit.
        user_id: Optional user identifier.

    Yields:
        AuditContext object with set_output() method.
    """
    class AuditContext:
        def __init__(self):
            self.output_data = None
            self.success = False
            self.tokens_input = 0
            self.tokens_output = 0
            self.cost_usd = 0.0

        def set_output(self, data: Any, tokens_input: int = 0, tokens_output: int = 0, cost_usd: float = 0.0):
            """Set output data and mark operation as successful.

            Args:
                data: Output data to audit
                tokens_input: Number of input tokens (LLM) - Week 4 Commit 26
                tokens_output: Number of output tokens (LLM) - Week 4 Commit 26
                cost_usd: Estimated cost in USD - Week 4 Commit 26
            """
            self.output_data = data
            self.success = True
            self.tokens_input = tokens_input
            self.tokens_output = tokens_output
            self.cost_usd = cost_usd

    ctx = AuditContext()
    start_time = time.perf_counter()

    try:
        yield ctx
    except Exception:
        # Operation failed, keep success=False
        ctx.output_data = {"error": "Operation failed"}
        raise
    finally:
        # Calculate duration
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Log audit record
        try:
            log_audit_record(
                correlation_id=correlation_id,
                tool=tool,
                action=action,
                input_data=input_data,
                output_data=ctx.output_data or {},
                success=ctx.success,
                duration_ms=duration_ms,
                tokens_input=ctx.tokens_input,
                tokens_output=ctx.tokens_output,
                cost_usd=ctx.cost_usd,
                user_id=user_id
            )
        except Exception as e:
            # Don't fail the operation if audit logging fails
            # In production, this would log to error monitoring
            print(f"Audit logging failed: {e}")


def get_audit_records(
    correlation_id: Optional[str] = None,
    limit: int = 100
) -> list[dict[str, Any]]:
    """Retrieve audit records from the database.

    Args:
        correlation_id: Optional filter by correlation ID.
        limit: Maximum number of records to return.

    Returns:
        List of audit record dictionaries.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            if correlation_id:
                cur.execute(
                    """
                    SELECT id, ts, correlation_id, user_id, tool, action,
                           input_hash, output_hash, success, duration_ms
                    FROM audit_log
                    WHERE correlation_id = %s
                    ORDER BY ts DESC
                    LIMIT %s
                    """,
                    (correlation_id, limit)
                )
            else:
                cur.execute(
                    """
                    SELECT id, ts, correlation_id, user_id, tool, action,
                           input_hash, output_hash, success, duration_ms
                    FROM audit_log
                    ORDER BY ts DESC
                    LIMIT %s
                    """,
                    (limit,)
                )

            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            return [dict(zip(columns, row)) for row in rows]
