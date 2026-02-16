from pydantic import BaseModel, Field
from typing import Any, Literal, Optional

ToolName = Literal["sql", "vector", "rest", "unknown"]

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    user_id: Optional[str] = None

class QueryResponse(BaseModel):
    tool_used: ToolName
    confidence: float = Field(..., ge=0.0, le=1.0)
    result: Any
    trace_id: str
    cost_usd: float = 0.0
    notes: Optional[str] = None

