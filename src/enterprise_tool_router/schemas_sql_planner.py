"""Pydantic schemas for SQL Planner output.

Week 3 Commit 17: SQL Planner
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator


class SqlPlanSchema(BaseModel):
    """Structured output schema for SQL planner.

    The LLM must return JSON matching this schema.
    All fields are validated and the schema is immutable.

    Constraints:
    - sql must be non-empty
    - confidence must be between 0.0 and 1.0
    - explanation must be non-empty
    """
    sql: str = Field(
        ...,
        min_length=1,
        description="Generated SQL query with LIMIT clause",
        examples=["SELECT region, SUM(revenue) FROM sales_fact GROUP BY region LIMIT 200"]
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the generated SQL (0.0-1.0)",
        examples=[0.95]
    )
    explanation: str = Field(
        ...,
        min_length=1,
        description="Human-readable explanation of what the SQL does",
        examples=["Aggregates revenue by region from sales fact table"]
    )

    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        json_schema_extra={
            "examples": [
                {
                    "sql": "SELECT region, quarter, revenue FROM sales_fact WHERE quarter = 'Q4' LIMIT 200",
                    "confidence": 0.92,
                    "explanation": "Filters sales data to Q4 results with default limit for safety"
                }
            ]
        }
    )

    @field_validator('sql')
    @classmethod
    def sql_must_contain_limit(cls, v: str) -> str:
        """Validate that SQL contains a LIMIT clause.

        This is a critical safety requirement. The LLM must always
        include a LIMIT to prevent unbounded queries.

        Args:
            v: SQL string to validate

        Returns:
            The validated SQL string

        Raises:
            ValueError: If LIMIT is not present
        """
        if 'LIMIT' not in v.upper():
            raise ValueError('SQL must contain a LIMIT clause for safety')
        return v


class SqlPlanErrorSchema(BaseModel):
    """Schema for SQL planner errors.

    Used when the planner cannot generate valid SQL.
    """
    error: str = Field(
        ...,
        description="Error message describing why SQL generation failed"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 for errors)"
    )

    model_config = ConfigDict(frozen=True)
