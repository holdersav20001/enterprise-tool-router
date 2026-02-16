from __future__ import annotations
import os
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from .schemas import ToolName
from .tools.sql import SqlTool
from .tools.vector import VectorTool
from .tools.rest import RestTool
from .tools.base import ToolResult
from .llm.base import LLMProvider
from .llm.providers import KilocodeProvider

@dataclass
class Routed:
    tool: ToolName
    confidence: float
    result: ToolResult
    elapsed_ms: float

class ToolRouter:
    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        """Initialize the tool router.

        Args:
            llm_provider: Optional LLM provider for natural language queries.
                         If None, attempts to create KilocodeProvider from env vars.
                         If KILOCODE_API_KEY is not set, SqlTool will only support raw SQL.
        """
        # If no provider specified, try to create KilocodeProvider from environment
        if llm_provider is None and os.getenv("KILOCODE_API_KEY"):
            try:
                llm_provider = KilocodeProvider()
            except Exception:
                # If Kilocode initialization fails, continue without LLM provider
                llm_provider = None

        self.tools: Dict[ToolName, object] = {
            "sql": SqlTool(llm_provider=llm_provider),
            "vector": VectorTool(),
            "rest": RestTool(),
        }

    def route(self, query: str) -> Tuple[ToolName, float]:
        # Week 1 deterministic heuristic router (LLM comes Week 2)
        q = query.lower()
        if any(k in q for k in ["select", "from", "group by", "revenue", "count", "sum"]) or "sql" in q:
            return "sql", 0.75
        if any(k in q for k in ["runbook", "docs", "how do i", "procedure", "playbook"]) or "doc" in q:
            return "vector", 0.70
        if any(k in q for k in ["call api", "endpoint", "http", "status", "service"]) or "api" in q:
            return "rest", 0.70
        return "unknown", 0.30

    def handle(self, query: str, correlation_id: str | None = None) -> Routed:
        """Route and execute a query with the appropriate tool.

        Args:
            query: The user query to route and execute
            correlation_id: Optional correlation ID for tracing. Auto-generates UUID if not provided.

        Returns:
            Routed object with tool name, confidence, result, and elapsed time
        """
        # Generate correlation ID if not provided
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        start = time.perf_counter()
        tool_name, conf = self.route(query)
        if tool_name == "unknown":
            res = ToolResult(data={"message": "No confident tool match", "query": query}, notes="unknown")
        else:
            res = self.tools[tool_name].run(query, correlation_id=correlation_id)  # type: ignore[index]
        elapsed = (time.perf_counter() - start) * 1000
        return Routed(tool=tool_name, confidence=conf, result=res, elapsed_ms=elapsed)

