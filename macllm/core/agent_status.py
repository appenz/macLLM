"""Agent status management for displaying plan, facts, and tool call progress."""

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional
import time


@dataclass
class ToolCallEntry:
    """A single tool call with its execution status."""
    id: str
    name: str
    args_summary: str
    status: Literal["running", "success", "error"]
    result_summary: str = ""
    started_at: float = field(default_factory=time.time)


class AgentStatusManager:
    """Manages structured status data during agent execution.
    
    Tracks three types of information:
    - plan: Current execution plan from planning steps
    - facts: Accumulated facts learned during execution
    - tool_calls: Log of all tool invocations with status
    """
    
    def __init__(self, ui_update_callback: Optional[Callable[[], None]] = None):
        self.ui_update_callback = ui_update_callback
        self.reset()
    
    def reset(self) -> None:
        """Clear all state for a new agent run."""
        self.plan = ""
        self.tool_calls: list[ToolCallEntry] = []
    
    def set_plan(self, plan: str) -> None:
        """Update the current plan."""
        self.plan = plan
        self._notify()
    
    def start_tool_call(self, id: str, name: str, args: dict) -> None:
        """Record the start of a tool call."""
        args_summary = _format_args_summary(name, args)
        entry = ToolCallEntry(
            id=id,
            name=name,
            args_summary=args_summary,
            status="running"
        )
        self.tool_calls.append(entry)
        self._notify()
    
    def complete_tool_call(self, id: str, result: str = "") -> None:
        """Mark a tool call as successfully completed.
        
        If no entry exists (instant tools that skip start_tool_call),
        creates a new entry with success status.
        """
        entry = self._find_entry(id)
        if entry:
            entry.status = "success"
            entry.result_summary = result[:100] if result else ""
        else:
            # Instant tool - create entry directly as success
            name = self._extract_tool_name(id)
            entry = ToolCallEntry(
                id=id,
                name=name,
                args_summary="",
                status="success",
                result_summary=result[:100] if result else ""
            )
            self.tool_calls.append(entry)
        self._notify()
    
    def fail_tool_call(self, id: str, error: str) -> None:
        """Mark a tool call as failed.
        
        If no entry exists, creates a new entry with error status.
        """
        entry = self._find_entry(id)
        if entry:
            entry.status = "error"
            entry.result_summary = error[:100] if error else "Unknown error"
        else:
            # Create entry directly as error
            name = self._extract_tool_name(id)
            entry = ToolCallEntry(
                id=id,
                name=name,
                args_summary="",
                status="error",
                result_summary=error[:100] if error else "Unknown error"
            )
            self.tool_calls.append(entry)
        self._notify()
    
    def render(self) -> str:
        """Render all sections for display."""
        sections = []
        
        if self.plan:
            sections.append(f"--- Plan ---\n{self.plan}")
        
        if self.tool_calls:
            lines = ["--- Tool Calls ---"]
            for entry in self.tool_calls:
                status_indicator = {
                    "running": "[..]",
                    "success": "[OK]",
                    "error": "[ERR]"
                }[entry.status]
                
                line = f"{status_indicator} {entry.name}({entry.args_summary})"
                if entry.status == "error" and entry.result_summary:
                    line += f" - {entry.result_summary}"
                lines.append(line)
            sections.append("\n".join(lines))
        
        return "\n\n".join(sections)
    
    def _find_entry(self, id: str) -> Optional[ToolCallEntry]:
        """Find a tool call entry by ID."""
        for entry in self.tool_calls:
            if entry.id == id:
                return entry
        return None
    
    def _extract_tool_name(self, id: str) -> str:
        """Extract tool name from ID format 'toolname_counter_timestamp'."""
        # ID format: "tool_name_1_1234567890"
        # Split from the right to handle tool names with underscores
        parts = id.rsplit("_", 2)
        if len(parts) >= 3:
            return parts[0]
        return id.split("_")[0] if "_" in id else id
    
    def _notify(self) -> None:
        """Trigger UI update callback if set."""
        if self.ui_update_callback:
            self.ui_update_callback()


def _format_args_summary(name: str, args: dict) -> str:
    """Format tool arguments for display, with special handling for known tools."""
    if not args:
        return ""
    
    if name == "web_search":
        queries = args.get("queries", [])
        if queries:
            queries_str = ", ".join(f'"{q}"' for q in queries[:2])
            if len(queries) > 2:
                queries_str += f" +{len(queries) - 2} more"
            return queries_str
    
    if name == "final_answer":
        answer = args.get("answer", "")
        return f'"{answer[:40]}..."' if len(answer) > 40 else f'"{answer}"'
    
    # Default: show first arg value truncated
    first_value = str(list(args.values())[0]) if args else ""
    if len(first_value) > 50:
        first_value = first_value[:47] + "..."
    return f'"{first_value}"'
