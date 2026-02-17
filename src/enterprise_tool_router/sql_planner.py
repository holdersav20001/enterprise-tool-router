"""SQL Planner - Natural Language to SQL using LLM.

This module uses an LLM to generate SQL queries from natural language.
The LLM proposes SQL, but the deterministic validator (from Week 2) approves it.

Week 3 Commit 17: SQL Planner

Architecture:
    Natural Language Query
         ↓
    LLM Provider (generate_structured)
         ↓
    SqlPlanSchema (Pydantic validation)
         ↓
    Return (sql, confidence, explanation)

Safety:
- LLM output is validated against strict Pydantic schema
- LIMIT clause is required in all generated SQL
- Output is immutable (frozen=True)
- No raw LLM output is returned
"""
from typing import Optional
from pydantic import ValidationError

from .llm.base import LLMProvider, StructuredOutputError, LLMTimeoutError, LLMUsage
from .schemas_sql_planner import SqlPlanSchema, SqlPlanErrorSchema
from .circuit_breaker import CircuitBreaker
from .cache import CacheManager, NoOpCache


# Database schema description for the LLM
# This tells the LLM what tables and columns are available
DB_SCHEMA_DESCRIPTION = """
Available Tables:

1. sales_fact
   - id: integer (primary key)
   - region: varchar(50) - Geographic region (e.g., "North America", "Europe")
   - quarter: varchar(10) - Quarter identifier (e.g., "Q1", "Q2", "Q3", "Q4")
   - revenue: decimal(12,2) - Revenue amount in USD
   - units_sold: integer - Number of units sold
   - created_at: timestamp - Record creation timestamp

2. job_runs
   - id: integer (primary key)
   - job_name: varchar(100) - Name of the ETL job
   - status: varchar(20) - Job status: 'success', 'failure', or 'running'
   - started_at: timestamp - Job start time
   - completed_at: timestamp - Job completion time (null if running)
   - records_processed: integer - Number of records processed

3. audit_log (read-only)
   - id: integer (primary key)
   - ts: timestamp - Timestamp of the operation
   - correlation_id: varchar(64) - Correlation ID for tracking
   - user_id: varchar(128) - User who performed the operation
   - tool: varchar(32) - Tool used (e.g., "sql", "vector", "rest")
   - action: varchar(64) - Action performed
   - input_hash: varchar(64) - SHA256 hash of input
   - output_hash: varchar(64) - SHA256 hash of output
   - success: boolean - Whether operation succeeded
   - duration_ms: integer - Duration in milliseconds

Allowed Tables: sales_fact, job_runs, audit_log
"""


class SqlPlanner:
    """Generate SQL queries from natural language using an LLM.

    The planner uses a structured output LLM to generate SQL that:
    - Matches the database schema
    - Includes a LIMIT clause for safety
    - Has a confidence score
    - Includes an explanation

    Example:
        >>> from enterprise_tool_router.llm.providers import MockProvider
        >>> provider = MockProvider(response_data={
        ...     "sql": "SELECT * FROM sales_fact LIMIT 10",
        ...     "confidence": 0.9,
        ...     "explanation": "Select all sales records"
        ... })
        >>> planner = SqlPlanner(provider)
        >>> result = planner.plan("Show me recent sales")
        >>> assert isinstance(result, SqlPlanSchema)
        >>> assert "LIMIT" in result.sql
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        circuit_breaker: Optional[CircuitBreaker] = None,
        cache_manager: Optional[CacheManager] = None
    ):
        """Initialize SQL planner with an LLM provider.

        Args:
            llm_provider: LLM provider to use for SQL generation
            circuit_breaker: Optional circuit breaker for fault tolerance (Week 4 Commit 22)
                            If None, creates default breaker (5 failures in 60s)
            cache_manager: Optional cache manager for caching responses (Week 4 Commit 23)
                          If None, creates default cache (5 min TTL, Redis if available)
        """
        self._llm = llm_provider
        # Week 4 Commit 22: Circuit breaker for fault tolerance
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=60.0,
            recovery_timeout=30.0
        )
        # Week 4 Commit 23: Caching for performance
        self._cache = cache_manager if cache_manager is not None else CacheManager(ttl_seconds=300)
        # Week 4 Commit 26: Track last LLM usage for cost metrics
        self._last_usage: Optional['LLMUsage'] = None

    def plan(
        self,
        natural_language_query: str,
        timeout: float = 30.0
    ) -> SqlPlanSchema | SqlPlanErrorSchema:
        """Generate SQL from a natural language query.

        Args:
            natural_language_query: User's query in natural language
            timeout: Maximum time to wait for LLM response in seconds (default: 30.0)
                     Week 4 Commit 21: Timeout protection

        Returns:
            SqlPlanSchema with generated SQL, confidence, and explanation
            OR SqlPlanErrorSchema if generation fails

        Example:
            >>> result = planner.plan("Show revenue by region", timeout=15.0)
            >>> if isinstance(result, SqlPlanSchema):
            ...     print(f"SQL: {result.sql}")
            ...     print(f"Confidence: {result.confidence}")
        """
        # Week 4 Commit 23: Check cache first (avoids LLM call)
        cached_response = self._cache.get(natural_language_query)
        if cached_response is not None:
            # Cache hit! Return cached SqlPlanSchema
            # Week 4 Commit 26: Cache hits have zero token usage
            self._last_usage = None
            # Reconstruct from dict
            try:
                return SqlPlanSchema(**cached_response)
            except Exception:
                # Cache corruption - proceed with LLM call
                pass

        # Week 4 Commit 22: Check circuit breaker before calling LLM
        if not self._circuit_breaker.can_execute():
            stats = self._circuit_breaker.get_stats()
            return SqlPlanErrorSchema(
                error=(
                    f"LLM service temporarily unavailable (circuit breaker {stats.state.value}). "
                    f"Multiple failures detected. Please try again in a moment or use raw SQL."
                ),
                confidence=0.0
            )

        try:
            # Build the prompt
            prompt = self._build_prompt(natural_language_query)

            # Generate structured output from LLM with timeout protection
            # Week 4 Commit 21: Pass timeout to prevent hanging
            plan, usage = self._llm.generate_structured(
                prompt,
                SqlPlanSchema,
                timeout=timeout
            )

            # Week 4 Commit 22: Record success with circuit breaker
            self._circuit_breaker.record_success()

            # Week 4 Commit 23: Cache successful response
            # Only cache SqlPlanSchema (not errors!)
            self._cache.set(natural_language_query, plan.model_dump())

            # Week 4 Commit 26: Track token usage for cost metrics
            self._last_usage = usage

            # plan is already validated by the LLM provider
            # and by SqlPlanSchema's field validators
            return plan

        except LLMTimeoutError as e:
            # Week 4 Commit 22: Timeout is a failure - record it
            self._circuit_breaker.record_failure()
            # Week 4 Commit 21: Graceful handling of timeout
            # System does not hang - returns safe error instead
            return SqlPlanErrorSchema(
                error=f"Query generation timed out after {timeout}s. Please try a simpler query or increase timeout.",
                confidence=0.0
            )
        except (StructuredOutputError, ValidationError) as e:
            # Week 4 Commit 22: Validation failures are LLM failures
            self._circuit_breaker.record_failure()
            # LLM output didn't match schema or validation failed
            return SqlPlanErrorSchema(
                error=f"Failed to generate valid SQL: {str(e)}",
                confidence=0.0
            )
        except Exception as e:
            # Week 4 Commit 22: All other errors are failures
            self._circuit_breaker.record_failure()
            # Other errors (API failures, etc.)
            return SqlPlanErrorSchema(
                error=f"SQL generation error: {str(e)}",
                confidence=0.0
            )

    def _build_prompt(self, query: str) -> str:
        """Build the prompt for the LLM.

        Args:
            query: Natural language query from the user

        Returns:
            Formatted prompt string with instructions and schema
        """
        prompt = f"""You are a SQL query generator for a PostgreSQL database.

DATABASE SCHEMA:
{DB_SCHEMA_DESCRIPTION}

SAFETY RULES (CRITICAL):
1. You MUST include a LIMIT clause in every query (default: LIMIT 200)
2. Only use SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
3. Only query the allowed tables listed above
4. Use proper SQL syntax for PostgreSQL

USER QUERY:
{query}

TASK:
Generate a safe SQL query that answers the user's question.

REQUIREMENTS:
- Return valid PostgreSQL SELECT query
- Include LIMIT clause (required for safety)
- Provide confidence score (0.0-1.0) based on query clarity
- Explain what the SQL does in plain English

If the query is unclear or cannot be safely translated to SQL, use a low confidence score (<0.7) and explain why in the explanation field.
"""
        return prompt

    @property
    def model_name(self) -> str:
        """Return the name of the underlying LLM model."""
        return self._llm.model_name

    @property
    def last_usage(self) -> Optional[LLMUsage]:
        """Return token usage from last LLM call.

        Week 4 Commit 26: Cost and token tracking.

        Returns:
            LLMUsage from last plan() call, or None if cache hit or error.
        """
        return self._last_usage
