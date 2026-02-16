from .base import ToolResult

class RestTool:
    name = "rest"

    def run(self, query: str) -> ToolResult:
        # Week 1: stub
        return ToolResult(data={"message": "REST tool stub", "query": query})

