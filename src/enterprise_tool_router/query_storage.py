"""Permanent query storage with configurable retention.

Week 4 Commit 27: Query History Storage

Provides functions to store and retrieve successful SQL queries with
automatic cleanup based on retention policy.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any
from .db import get_connection

DEFAULT_RETENTION_DAYS = 30  # Configurable retention period


def store_query(
    natural_language_query: str,
    generated_sql: str,
    confidence: float,
    result_size_bytes: int,
    row_count: int,
    execution_time_ms: int,
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_usd: float = 0.0,
    user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    retention_days: int = DEFAULT_RETENTION_DAYS
) -> None:
    """Store a successful query in the query_history table.

    Args:
        natural_language_query: Original user query
        generated_sql: Validated SQL that was executed
        confidence: Planner confidence score (0.0-1.0)
        result_size_bytes: Size of serialized results
        row_count: Number of rows returned
        execution_time_ms: Query execution time
        tokens_input: LLM input tokens
        tokens_output: LLM output tokens
        cost_usd: Estimated cost
        user_id: User who executed the query
        correlation_id: Trace ID for linking to audit_log
        retention_days: Days to keep the query (default: 30)
    """
    # Generate query hash for deduplication
    query_hash = _hash_query(natural_language_query)
    expires_at = datetime.utcnow() + timedelta(days=retention_days)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Upsert: update if exists, insert if new
            cur.execute("""
                INSERT INTO query_history (
                    query_hash, natural_language_query, generated_sql,
                    confidence, result_size_bytes, row_count,
                    execution_time_ms, tokens_input, tokens_output,
                    cost_usd, user_id, correlation_id,
                    created_at, last_used_at, use_count, expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, %s)
                ON CONFLICT (query_hash) DO UPDATE SET
                    last_used_at = CURRENT_TIMESTAMP,
                    use_count = query_history.use_count + 1,
                    expires_at = %s
                """, (
                    query_hash, natural_language_query, generated_sql,
                    confidence, result_size_bytes, row_count,
                    execution_time_ms, tokens_input, tokens_output,
                    cost_usd, user_id, correlation_id, expires_at, expires_at
                ))
        conn.commit()


def get_query_by_hash(query_hash: str) -> Optional[dict[str, Any]]:
    """Retrieve a query from history by its hash.

    Args:
        query_hash: SHA256 hash of the query

    Returns:
        Dict with query details or None if not found/expired
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    natural_language_query, generated_sql, confidence,
                    result_size_bytes, row_count, execution_time_ms,
                    tokens_input, tokens_output, cost_usd,
                    user_id, correlation_id, created_at, last_used_at,
                    use_count
                FROM query_history
                WHERE query_hash = %s AND expires_at > CURRENT_TIMESTAMP
                """, (query_hash,))
            row = cur.fetchone()

            if row is None:
                return None

            return {
                "natural_language_query": row[0],
                "generated_sql": row[1],
                "confidence": float(row[2]),
                "result_size_bytes": row[3],
                "row_count": row[4],
                "execution_time_ms": row[5],
                "tokens_input": row[6],
                "tokens_output": row[7],
                "cost_usd": float(row[8]),
                "user_id": row[9],
                "correlation_id": row[10],
                "created_at": row[11],
                "last_used_at": row[12],
                "use_count": row[13]
            }


def lookup_query(natural_language_query: str) -> Optional[dict[str, Any]]:
    """Look up a query by its natural language text.

    Convenience wrapper around get_query_by_hash().

    Args:
        natural_language_query: User's original query

    Returns:
        Dict with query details or None if not found
    """
    query_hash = _hash_query(natural_language_query)
    return get_query_by_hash(query_hash)


def cleanup_expired_queries() -> int:
    """Delete queries that have passed their retention period.

    Should be called periodically (e.g., daily cron job).

    Returns:
        Number of queries deleted
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM query_history
                WHERE expires_at <= CURRENT_TIMESTAMP
                """)
            deleted_count = cur.rowcount
        conn.commit()

    return deleted_count


def _hash_query(query: str) -> str:
    """Generate SHA256 hash of normalized query.

    Matches cache.py key generation logic for consistency.
    """
    normalized = query.lower().strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
