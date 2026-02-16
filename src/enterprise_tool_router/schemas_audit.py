"""Pydantic schemas for audit log records."""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class AuditRecordSchema(BaseModel):
    """Schema for audit log records.

    Represents a single audit trail entry for query operations.
    All audit records are append-only (no updates or deletes).
    """
    id: int = Field(..., description="Unique audit record ID")
    ts: datetime = Field(..., description="Timestamp of the operation")
    correlation_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Request correlation ID for tracing"
    )
    user_id: Optional[str] = Field(
        None,
        max_length=128,
        description="User who initiated the operation"
    )
    tool: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Tool used (sql, vector, rest)"
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Action performed"
    )
    input_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA256 hash of input data"
    )
    output_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA256 hash of output data"
    )
    success: bool = Field(
        ...,
        description="Whether the operation succeeded"
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Operation duration in milliseconds"
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "ts": "2024-01-15T10:30:00Z",
                    "correlation_id": "trace-abc-123",
                    "user_id": "user@example.com",
                    "tool": "sql",
                    "action": "query",
                    "input_hash": "a" * 64,
                    "output_hash": "b" * 64,
                    "success": True,
                    "duration_ms": 125
                }
            ]
        }
    )
