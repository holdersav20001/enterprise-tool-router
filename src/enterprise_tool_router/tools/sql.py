from .base import ToolResult

class SqlTool:
    name = "sql"

    def run(self, query: str) -> ToolResult:
        # Week 1: stub (no DB wiring yet)
        return ToolResult(data={"message": "SQL tool stub", "query": query})

