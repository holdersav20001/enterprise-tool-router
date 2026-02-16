from .base import ToolResult

class RestTool:
    name = "rest"

    def run(self, query: str, correlation_id: str = "unknown") -> ToolResult:
        """Execute REST API call.

        Args:
            query: API request specification
            correlation_id: Correlation ID for tracing requests across layers

        Returns:
            ToolResult with API response
        """
        # Week 1: stub
        return ToolResult(data={"message": "REST tool stub", "query": query})

