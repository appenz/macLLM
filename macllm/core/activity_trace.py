from __future__ import annotations

import itertools
import math
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator, Literal


ActivityState = Literal["running", "success", "error"]


@dataclass
class ActivityNode:
    """A single query activity with inclusive children and exclusive metrics."""

    id: int
    label: str
    kind: str = "activity"
    state: ActivityState = "running"
    started_at: float = 0.0
    finished_at: float | None = None
    self_input_tokens: int = 0
    self_output_tokens: int = 0
    result_tokens: int = 0
    parent: ActivityNode | None = field(default=None, repr=False)
    children: list[ActivityNode] = field(default_factory=list)

    @property
    def self_tokens(self) -> int:
        return self.self_input_tokens + self.self_output_tokens

    @property
    def total_tokens(self) -> int:
        return self.self_tokens + sum(child.total_tokens for child in self.children)

    def self_time(self, now: float | None = None) -> float:
        child_total = sum(child.total_time(now) for child in self.children)
        if self.kind == "model":
            return self._elapsed(now)
        return max(0.0, self.total_time(now) - child_total)

    def total_time(self, now: float | None = None) -> float:
        child_total = sum(child.total_time(now) for child in self.children)
        elapsed = self._elapsed(now)
        if self.kind == "model":
            return elapsed + child_total
        return max(elapsed, child_total)

    def _elapsed(self, now: float | None = None) -> float:
        if self.started_at < 0:
            return 0.0
        end = self.finished_at
        if end is None:
            end = now if now is not None else time.monotonic()
        return max(0.0, end - self.started_at)

    def add_tokens(self, token_usage) -> None:
        if token_usage is None:
            return
        self.self_input_tokens += int(getattr(token_usage, "input_tokens", 0) or 0)
        self.self_output_tokens += int(getattr(token_usage, "output_tokens", 0) or 0)

    def add_result(self, result) -> None:
        self.result_tokens += estimate_text_tokens(result)


class ActivityTrace:
    """Transient, per-query activity tree for UI progress and debug summaries."""

    def __init__(
        self,
        label: str = "agent",
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self._ids = itertools.count(1)
        self.root = ActivityNode(
            id=next(self._ids),
            label=label,
            kind="root",
            started_at=self._clock(),
        )
        self._stack: list[ActivityNode] = [self.root]

    @property
    def has_activity(self) -> bool:
        return bool(self.root.children)

    def finish(self, state: ActivityState = "success") -> None:
        now = self._clock()
        while len(self._stack) > 1:
            self._close_node(self._stack[-1], state=state, now=now)
        self._close_node(self.root, state=state, now=now)

    @contextmanager
    def scoped_node(
        self,
        label: str,
        *,
        kind: str = "activity",
    ) -> Iterator[ActivityNode]:
        node = self.open_node(label, kind=kind)
        try:
            yield node
        except Exception:
            self.close_node(node, state="error")
            raise
        else:
            self.close_node(node, state="success")

    def open_node(self, label: str, *, kind: str = "activity") -> ActivityNode:
        node = ActivityNode(
            id=next(self._ids),
            label=label,
            kind=kind,
            started_at=self._clock(),
            parent=self._stack[-1],
        )
        self._stack[-1].children.append(node)
        self._stack.append(node)
        return node

    def close_node(self, node: ActivityNode, *, state: ActivityState = "success") -> None:
        self._close_node(node, state=state, now=self._clock())

    def discard_node(self, node: ActivityNode) -> None:
        """Remove a transient node, used when a live row is replaced."""
        if node in self._stack:
            while self._stack and self._stack[-1] is not node:
                self._stack.pop()
            if self._stack and self._stack[-1] is node:
                self._stack.pop()
        if node.parent is not None and node in node.parent.children:
            node.parent.children.remove(node)
        if not self._stack:
            self._stack.append(self.root)

    def record_tool_result(self, node: ActivityNode | None, result) -> None:
        if node is not None:
            node.add_result(result)

    def start_model_call(self, label: str = "Thinking") -> ActivityNode:
        return self.open_node(label, kind="model")

    def finish_model_call(self, node: ActivityNode, *, state: ActivityState = "success") -> None:
        # Leave the node on the stack after the LLM returns so tool/subagent
        # activity caused by that model decision can be nested below it.
        if state == "error":
            node.state = "error"
        if node.finished_at is None:
            node.finished_at = self._clock()

    def close_current_model_step(
        self,
        *,
        label: str | None = None,
        token_usage=None,
        state: ActivityState = "success",
    ) -> ActivityNode:
        node = self._current_model_node()
        if node is None:
            node = self.open_node(label or "Thinking", kind="model")
        if label:
            node.label = label
        node.add_tokens(token_usage)
        self._close_node(node, state=state, now=self._clock())
        return node

    def update_current_model_step(
        self,
        *,
        label: str | None = None,
        token_usage=None,
    ) -> ActivityNode:
        node = self._current_model_node()
        if node is None:
            node = self.open_node(label or "Thinking", kind="model")
        if label:
            node.label = label
        node.add_tokens(token_usage)
        return node

    def record_model_step(
        self,
        label: str,
        *,
        token_usage=None,
        state: ActivityState = "success",
    ) -> ActivityNode:
        node = self.open_node(label, kind="model")
        node.add_tokens(token_usage)
        self._close_node(node, state=state, now=self._clock())
        return node

    def _current_model_node(self) -> ActivityNode | None:
        for node in reversed(self._stack):
            if node.kind == "model":
                return node
        return None

    def _close_node(self, node: ActivityNode, *, state: ActivityState, now: float) -> None:
        node.state = state
        if node.finished_at is None:
            node.finished_at = now
        if node in self._stack:
            while self._stack and self._stack[-1] is not node:
                orphan = self._stack[-1]
                orphan.state = state
                if orphan.finished_at is None:
                    orphan.finished_at = now
                self._stack.pop()
            if self._stack and self._stack[-1] is node:
                self._stack.pop()
        if not self._stack:
            self._stack.append(self.root)

    def format_ui_lines(self, *, width: int = 60, unicode: bool = True) -> list[str]:
        return _format_tree(
            self.root.children,
            width=width,
            unicode=unicode,
            metrics="ui",
            now=self._clock(),
        )

    def format_debug_summary(
        self,
        *,
        query: str | None = None,
        width: int = 60,
        unicode: bool = True,
    ) -> str:
        title = "Activity summary"
        if query:
            cropped = crop_text(" ".join(query.split()), max(0, width - len(title) - 2))
            title = f"{title}: {cropped}"
        lines = [crop_text(title, width)]
        lines.extend(
            _format_tree(
                [self.root],
                width=width,
                unicode=unicode,
                metrics="debug",
                now=self._clock(),
                compact=width <= 72,
            )
        )
        return "\n".join(lines)


def compact_tokens(tokens: int) -> str:
    if tokens <= 0:
        return "0"
    if tokens < 1000:
        return str(tokens)
    if tokens < 1_000_000:
        return f"{tokens / 1000:.1f}k"
    return f"{tokens / 1_000_000:.1f}M"


def estimate_text_tokens(value) -> int:
    """Estimate tokens for local tool results without requiring a tokenizer."""
    if value is None:
        return 0
    text = value if isinstance(value, str) else str(value)
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def compact_time(seconds: float) -> str:
    if seconds < 10:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 10:
        return f"{minutes:.1f}m"
    return f"{minutes:.0f}m"


def crop_text(text: str, width: int, *, middle: bool = False) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width
    if middle:
        left = (width - 3) // 2
        right = width - 3 - left
        return f"{text[:left]}...{text[-right:]}"
    return f"{text[:width - 3]}..."


def _format_tree(
    nodes: list[ActivityNode],
    *,
    width: int,
    unicode: bool,
    metrics: Literal["ui", "debug"],
    now: float,
    prefix: str = "",
    compact: bool = False,
) -> list[str]:
    lines: list[str] = []
    for index, node in enumerate(nodes):
        last = index == len(nodes) - 1
        connector = _connector(last, unicode, compact=compact)
        child_prefix = prefix + _child_prefix(last, unicode, compact=compact)
        lines.append(_format_line(node, prefix + connector, width=width, metrics=metrics, now=now, compact=compact))
        lines.extend(
            _format_tree(
                node.children,
                width=width,
                unicode=unicode,
                metrics=metrics,
                now=now,
                prefix=child_prefix,
                compact=compact,
            )
        )
    return lines


def _format_line(
    node: ActivityNode,
    leader: str,
    *,
    width: int,
    metrics: Literal["ui", "debug"],
    now: float,
    compact: bool = False,
) -> str:
    metric_text = _metric_text(node, metrics=metrics, now=now)
    label = f"{_state_symbol(node.state)} {node.label}" if metrics == "ui" else node.label
    separator = "  "
    available = width - len(leader) - len(separator) - len(metric_text)
    if available < 4:
        metric_text = _metric_text(node, metrics=metrics, now=now, short=True)
        available = width - len(leader) - len(separator) - len(metric_text)
    if available < len(label) and label in {"Planning", "Thinking", "Final answer"}:
        metric_text = _metric_text(node, metrics=metrics, now=now, short=True, minimal=True)
        available = width - len(leader) - len(separator) - len(metric_text)
    if available < 4:
        metric_text = ""
        separator = ""
        available = width - len(leader)
    label = crop_text(label, max(0, available), middle=(metrics == "debug"))
    line = f"{leader}{label}{separator}{metric_text}" if metric_text else f"{leader}{label}"
    return crop_text(line, width)


def _metric_text(
    node: ActivityNode,
    *,
    metrics: Literal["ui", "debug"],
    now: float,
    short: bool = False,
    minimal: bool = False,
) -> str:
    if metrics == "ui":
        if node.state == "running" and node.total_tokens == 0:
            return "..."
        return f"{compact_tokens(node.total_tokens)} tok · {compact_time(node.total_time(now))}"
    if node.kind in {"agent", "root"}:
        return f"total {compact_tokens(node.total_tokens)}/{compact_time(node.total_time(now))}"
    if node.kind == "tool":
        if node.result_tokens:
            return f"result {compact_tokens(node.result_tokens)}/{compact_time(node.self_time(now))}"
        return f"self {compact_tokens(node.self_tokens)}/{compact_time(node.self_time(now))}"
    if minimal:
        return f"{compact_tokens(node.self_tokens)}/{compact_time(node.self_time(now))}"
    if short:
        return f"s {compact_tokens(node.self_tokens)}/{compact_time(node.self_time(now))}"
    return f"self {compact_tokens(node.self_tokens)}/{compact_time(node.self_time(now))}"


def _state_symbol(state: ActivityState) -> str:
    if state == "success":
        return "✓"
    if state == "error":
        return "✗"
    return "⟳"


def _connector(last: bool, unicode: bool, *, compact: bool = False) -> str:
    if unicode:
        if compact:
            return "└ " if last else "├ "
        return "└─ " if last else "├─ "
    if compact:
        return "` " if last else "| "
    return "`- " if last else "|- "


def _child_prefix(last: bool, unicode: bool, *, compact: bool = False) -> str:
    if unicode:
        if compact:
            return "  " if last else "│ "
        return "   " if last else "│  "
    if compact:
        return "  " if last else "| "
    return "   " if last else "|  "
