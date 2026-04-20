"""Pending approval dataclass for shell command approval flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional
import threading


@dataclass
class PendingApproval:
    """Tracks a shell command awaiting user approval."""
    command: str
    unknown_executables: list[str]
    tool_call_id: str
    ungranted_paths: list[str] = field(default_factory=list)
    event: threading.Event = field(default_factory=threading.Event)
    decision: Optional[Literal["run", "deny", "always_allow", "grant_home"]] = None
