"""Pydantic schemas for SQL tool output."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Any


class SqlResultSchema(BaseModel):
    """Structured output schema for SQL query results.

    Ensures no raw database driver objects leak into API responses.
    All data is serializable and stable across database driver changes.
    """
    columns: list[str] = Field(
        ...,
        description="Column names from the query result",
        examples=[["region", "quarter", "revenue"]]
    )
    rows: list[list[Any]] = Field(
        ...,
        description="Query result rows as lists of values",
        examples=[[["North America", "Q1", 1250000.00]]]
    )
    row_count: int = Field(
        ...,
        ge=0,
        description="Number of rows returned",
        examples=[3]
    )

    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        json_schema_extra={
            "examples": [
                {
                    "columns": ["region", "quarter", "revenue"],
                    "rows": [
                        ["North America", "Q1", 1250000.00],
                        ["North America", "Q2", 1380000.00],
                        ["Europe", "Q1", 950000.00]
                    ],
                    "row_count": 3
                }
            ]
        }
    )


class SqlErrorSchema(BaseModel):
    """Schema for SQL tool errors.

    Used when safety violations or execution errors occur.
    """
    error: str = Field(
        ...,
        description="Error message describing what went wrong",
        examples=["Only SELECT statements are allowed"]
    )

    model_config = ConfigDict(frozen=True)
