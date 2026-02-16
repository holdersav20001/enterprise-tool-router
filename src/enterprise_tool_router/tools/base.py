from dataclasses import dataclass
from typing import Protocol, Any

@dataclass(frozen=True)
class ToolResult:
    data: Any
    notes: str = ""

class Tool(Protocol):
    name: str
    def run(self, query: str) -> ToolResult: ...

