from .base import ToolResult

class VectorTool:
    name = "vector"

    def run(self, query: str) -> ToolResult:
        # Week 1: stub
        return ToolResult(data={"message": "Vector tool stub", "query": query})

