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
from .llm.providers import OpenRouterProvider, KilocodeProvider
from .rate_limiter import RateLimiter, RateLimitError

@dataclass
class Routed:
    tool: ToolName
    confidence: float
    result: ToolResult
    elapsed_ms: float

class ToolRouter:
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        rate_limiter: Optional[RateLimiter] = None
    ) -> None:
        """Initialize the tool router.

        Args:
            llm_provider: Optional LLM provider for natural language queries.
                         If None, attempts to create provider from env vars:
                         1. OpenRouterProvider (if OPENROUTER_API_KEY is set)
                         2. KilocodeProvider (if KILOCODE_API_KEY is set)
                         If no keys are set, SqlTool will only support raw SQL.
            rate_limiter: Optional rate limiter for request throttling (Week 4 Commit 24)
                         If None, creates default limiter (100 requests per minute)
        """
        # If no provider specified, try to auto-detect from environment
        if llm_provider is None:
            # Try OpenRouter first (recommended)
            if os.getenv("OPENROUTER_API_KEY"):
                try:
                    llm_provider = OpenRouterProvider()
                except Exception:
                    llm_provider = None
            # Fall back to Kilocode if available
            elif os.getenv("KILOCODE_API_KEY"):
                try:
                    llm_provider = KilocodeProvider()
                except Exception:
                    llm_provider = None

        self.tools: Dict[ToolName, object] = {
            "sql": SqlTool(llm_provider=llm_provider),
            "vector": VectorTool(),
            "rest": RestTool(),
        }

        # Week 4 Commit 24: Rate limiting for abuse prevention
        self._rate_limiter = rate_limiter or RateLimiter(
            max_requests=100,
            window_seconds=60
        )

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

    def handle(
        self,
        query: str,
        correlation_id: str | None = None,
        user_id: str | None = None
    ) -> Routed:
        """Route and execute a query with the appropriate tool.

        Args:
            query: The user query to route and execute
            correlation_id: Optional correlation ID for tracing. Auto-generates UUID if not provided.
            user_id: Optional user/IP identifier for rate limiting (Week 4 Commit 24)

        Returns:
            Routed object with tool name, confidence, result, and elapsed time
        """
        # Week 4 Commit 24: Check rate limit first
        if user_id and self._rate_limiter.is_enabled:
            try:
                self._rate_limiter.check_limit(user_id)
                # Record successful request
                self._rate_limiter.record_request(user_id)
            except RateLimitError as e:
                # Return structured error response
                error_data = {
                    "error": "Rate limit exceeded",
                    "message": str(e),
                    "limit": e.limit,
                    "window_seconds": e.window,
                    "retry_after_seconds": e.retry_after,
                    "identifier": e.identifier
                }
                res = ToolResult(data=error_data, notes="rate_limit_exceeded")
                return Routed(
                    tool="unknown",
                    confidence=0.0,
                    result=res,
                    elapsed_ms=0.0
                )

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

