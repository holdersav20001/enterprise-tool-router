import uuid
from .base import ToolResult

class RestTool:
    name = "rest"

    def run(self, query: str, correlation_id: str | None = None) -> ToolResult:
        """Execute REST API call.

        Args:
            query: API request specification
            correlation_id: Optional correlation ID for tracing. Auto-generates UUID if not provided.

        Returns:
            ToolResult with API response
        """
        # Generate correlation ID if not provided
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        # Week 1: stub
        return ToolResult(data={"message": "REST tool stub", "query": query})

