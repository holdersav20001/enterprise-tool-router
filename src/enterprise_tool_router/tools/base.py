from dataclasses import dataclass
from typing import Protocol, Any

@dataclass(frozen=True)
class ToolResult:
    data: Any
    notes: str = ""

class Tool(Protocol):
    name: str
    def run(self, query: str, correlation_id: str | None = None) -> ToolResult:
        """Execute the tool with the given query.

        Args:
            query: The query string to execute
            correlation_id: Optional correlation ID for tracing. Auto-generates UUID if not provided.

        Returns:
            ToolResult with execution results
        """
        ...

