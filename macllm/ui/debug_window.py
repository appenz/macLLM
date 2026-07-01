from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import AppKit
from Cocoa import (
    NSAttributedString,
    NSButton,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSLinkAttributeName,
    NSMutableAttributedString,
    NSObject,
    NSPanel,
    NSScreen,
    NSScrollView,
    NSTextView,
)


@dataclass
class DebugCard:
    id: str
    title: str
    body: str
    step_tokens: str = "-"
    total_tokens: str = "-"
    step_time: str = "-"
    total_time: str = "-"
    expanded_by_default: bool = False


class DebugWindowPanel(NSPanel):
    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True


class DebugWindowDelegate(NSObject):
    controller = None

    def textView_clickedOnLink_atIndex_(self, _view, link, _index):  # noqa: N802
        link_str = str(link)
        if link_str.startswith("macllm-debug://toggle/"):
            card_id = link_str.split("/")[-1]
            if self.controller:
                self.controller.toggle(card_id)
            return True
        return False

    def save_(self, _sender):
        if self.controller:
            self.controller.save()

    def windowWillClose_(self, _notification):  # noqa: N802
        if self.controller:
            self.controller.closed_by_user()


class DebugWindow:
    """Passive renderer for a conversation's chronological debug facts."""

    def __init__(self, macllm_ui):
        self.macllm_ui = macllm_ui
        self.panel = None
        self.text_view = None
        self.scroll_view = None
        self.save_button = None
        self.delegate = DebugWindowDelegate.alloc().init()
        self.delegate.controller = self
        self.conversation = None
        self.conv_id = None
        self.expanded_ids: set[str] = set()
        self.collapsed_ids: set[str] = set()

    def open(self, conversation):
        self.conversation = conversation
        self.conv_id = getattr(conversation, "conv_id", None)
        if self.panel is None:
            self._create_window()
        self.refresh()
        self.panel.orderFrontRegardless()
        self.panel.makeKeyWindow()

    def refresh(self):
        if self.panel is None or self.conversation is None:
            return
        cards = extract_cards(self.conversation)
        text = render_attributed_cards(cards, self.expanded_ids, self.collapsed_ids)
        self.text_view.textStorage().setAttributedString_(text)

    def toggle(self, card_id: str):
        if card_id in self.expanded_ids:
            self.expanded_ids.remove(card_id)
            self.collapsed_ids.add(card_id)
        else:
            self.expanded_ids.add(card_id)
            self.collapsed_ids.discard(card_id)
        self.refresh()

    def close_for_conversation(self, conv_id: str):
        if self.conv_id == conv_id:
            self.close()

    def close(self):
        if self.panel is not None:
            self.panel.orderOut_(None)
        self.panel = None
        self.text_view = None
        self.scroll_view = None
        self.save_button = None
        self.conversation = None
        self.conv_id = None

    def closed_by_user(self):
        self.panel = None
        self.text_view = None
        self.scroll_view = None
        self.save_button = None
        self.conversation = None
        self.conv_id = None
        if getattr(self.macllm_ui, "debug_window", None) is self:
            self.macllm_ui.debug_window = None

    def save(self):
        if self.conversation is None:
            return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.abspath(f"debug_log_{timestamp}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_markdown(self.conversation))

    def _create_window(self):
        screen = NSScreen.mainScreen().visibleFrame()
        width = int(self.macllm_ui.window_width * 1.2)
        height = int(screen.size.height)
        x = int(screen.origin.x + screen.size.width - width - 24)
        y = int(screen.origin.y)

        style = (
            _style_mask("NSWindowStyleMaskTitled", "NSTitledWindowMask")
            | _style_mask("NSWindowStyleMaskClosable", "NSClosableWindowMask")
            | _style_mask("NSWindowStyleMaskResizable", "NSResizableWindowMask")
        )
        backing = getattr(AppKit, "NSBackingStoreBuffered", 2)
        panel = DebugWindowPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (width, height)),
            style,
            backing,
            False,
        )
        panel.setTitle_("macLLM Debug Log")
        panel.setLevel_(3)
        panel.setDelegate_(self.delegate)

        save_button = NSButton.alloc().initWithFrame_(((12, height - 42), (72, 28)))
        save_button.setTitle_("Save")
        save_button.setTarget_(self.delegate)
        save_button.setAction_("save:")
        panel.contentView().addSubview_(save_button)

        scroll_view = NSScrollView.alloc().initWithFrame_(((12, 12), (width - 24, height - 60)))
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setHasHorizontalScroller_(False)
        scroll_view.setAutohidesScrollers_(False)

        text_view = NSTextView.alloc().initWithFrame_(((0, 0), (width - 48, height - 60)))
        text_view.setEditable_(False)
        text_view.setSelectable_(True)
        text_view.setDrawsBackground_(False)
        text_view.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11.0, 0.0))
        text_view.setDelegate_(self.delegate)
        text_view.setLinkTextAttributes_({})

        scroll_view.setDocumentView_(text_view)
        panel.contentView().addSubview_(scroll_view)

        self.panel = panel
        self.save_button = save_button
        self.scroll_view = scroll_view
        self.text_view = text_view


def extract_cards(conversation) -> list[DebugCard]:
    cards: list[DebugCard] = []
    total_input = 0
    total_output = 0
    total_time = 0.0
    log = list(getattr(conversation, "conversation_log", []))
    skip_indices: set[int] = set()
    suppress_assistant_text: str | None = None
    for index, item in enumerate(log):
        if index in skip_indices:
            continue
        kind = getattr(item, "kind", "")
        payload = getattr(item, "payload", None)
        card_id = f"{index}-{kind}"
        step_input, step_output = _step_tokens(payload)
        step_time = _step_seconds(kind, payload)
        total_input += step_input
        total_output += step_output
        if kind != "run_end":
            total_time += step_time
        header = {
            "step_tokens": _format_tokens(step_input, step_output),
            "total_tokens": _format_tokens(total_input, total_output),
            "step_time": _format_seconds(step_time),
            "total_time": _format_seconds(step_time if kind == "run_end" else total_time),
        }
        if kind == "message" and isinstance(payload, dict):
            role = str(payload.get("role", "message"))
            content = str(payload.get("content", ""))
            if role == "assistant" and _same_text(content, suppress_assistant_text):
                suppress_assistant_text = None
                continue
            title = "User Request" if role == "user" else "Assistant Response"
            body = content
            if role == "user":
                next_payload = _payload_at(log, index + 1, "run_start")
                if isinstance(next_payload, dict) and _same_text(content, next_payload.get("query")):
                    expanded = str(next_payload.get("expanded_prompt", "") or "")
                    body = _request_body(content, expanded)
                    skip_indices.add(index + 1)
            cards.append(DebugCard(
                id=card_id,
                title=title,
                **header,
                body=body,
                expanded_by_default=True,
            ))
        elif kind == "plan" and isinstance(payload, dict):
            # Parsed plan entries are merged into the preceding Planning Step.
            continue
        elif kind == "tool_call" and isinstance(payload, dict):
            cards.append(DebugCard(
                id=card_id,
                title=f"Live Tool: {payload.get('tool', 'tool')}",
                **header,
                body=str(payload.get("message", "")),
            ))
        elif kind == "run_start" and isinstance(payload, dict):
            body = _request_body(payload.get("query"), payload.get("expanded_prompt"))
            if not body.strip():
                continue
            cards.append(DebugCard(
                id=card_id,
                title="User Request",
                **header,
                body=body,
                expanded_by_default=True,
            ))
        elif kind == "step" and isinstance(payload, dict):
            if payload.get("step_type") == "planning":
                parsed_plan = _payload_at(log, index + 1, "plan")
                if isinstance(parsed_plan, dict):
                    skip_indices.add(index + 1)
                body = _planning_body(payload, parsed_plan)
            else:
                body = _runtime_body(kind, payload)
            if not body.strip():
                continue
            final_answer = _final_answer_text(payload)
            if final_answer:
                suppress_assistant_text = final_answer
            cards.append(DebugCard(
                id=card_id,
                title=_runtime_title(kind, payload),
                **header,
                body=body,
                expanded_by_default=bool(final_answer),
            ))
        elif kind == "run_end" and isinstance(payload, dict):
            body = _runtime_body(kind, payload)
            if body.strip():
                cards.append(DebugCard(
                    id=card_id,
                    title="Run Complete",
                    **header,
                    body=body,
                ))
        else:
            cards.append(DebugCard(
                id=card_id,
                title=kind or "Entry",
                **header,
                body=_format_value(payload),
            ))
    return cards


def render_attributed_cards(
    cards: list[DebugCard],
    expanded_ids: set[str],
    collapsed_ids: set[str],
) -> NSMutableAttributedString:
    text = NSMutableAttributedString.alloc().init()
    title_attrs = {
        NSFontAttributeName: NSFont.boldSystemFontOfSize_(12.0),
        NSForegroundColorAttributeName: NSColor.blackColor(),
    }
    meta_attrs = {
        NSFontAttributeName: NSFont.systemFontOfSize_(10.0),
        NSForegroundColorAttributeName: NSColor.grayColor(),
    }
    body_attrs = {
        NSFontAttributeName: NSFont.monospacedSystemFontOfSize_weight_(10.0, 0.0),
        NSForegroundColorAttributeName: NSColor.darkGrayColor(),
    }
    link_attrs = {
        NSFontAttributeName: NSFont.systemFontOfSize_(10.0),
        NSForegroundColorAttributeName: NSColor.grayColor(),
    }

    for card in cards:
        expanded = _is_expanded(card, expanded_ids, collapsed_ids)
        _append(text, f"{card.title}", title_attrs)
        _append(
            text,
            (
                f"  tokens: {card.step_tokens}"
                f"  total: {card.total_tokens}"
                f"  time: {card.step_time}"
                f"  total: {card.total_time}"
            ),
            meta_attrs,
        )
        _append(text, "\n", body_attrs)

        lines = card.body.splitlines() or [""]
        display_lines = lines if expanded else lines[:5]
        _append(text, "\n".join(display_lines) + "\n", body_attrs)
        if len(lines) > 5:
            link_text = "collapse" if expanded else f"expand ({len(lines) - 5} more lines)"
            attrs = dict(link_attrs)
            attrs[NSLinkAttributeName] = f"macllm-debug://toggle/{card.id}"
            _append(text, f"{link_text}\n", attrs)
        _append(text, "\n", body_attrs)
    return text


def render_markdown(conversation) -> str:
    cards = extract_cards(conversation)
    lines = [
        f"# Debug Log: {getattr(conversation, 'title', 'Conversation')}",
        "",
        f"- Conversation: `{getattr(conversation, 'conv_id', '')}`",
        f"- Saved: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for card in cards:
        lines.append(
            f"## {card.title} | tokens {card.step_tokens} | total {card.total_tokens}"
            f" | time {card.step_time} | total {card.total_time}"
        )
        lines.append("```text")
        lines.append(card.body)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _append(text, content: str, attrs: dict):
    text.appendAttributedString_(
        NSAttributedString.alloc().initWithString_attributes_(content, attrs)
    )


def _style_mask(modern: str, legacy: str) -> int:
    return getattr(AppKit, modern, getattr(AppKit, legacy, 0))


def _is_expanded(card: DebugCard, expanded_ids: set[str], collapsed_ids: set[str]) -> bool:
    if card.id in expanded_ids:
        return True
    if card.id in collapsed_ids:
        return False
    return card.expanded_by_default


def _runtime_title(kind: str, payload: dict) -> str:
    if kind == "run_start":
        return "Request"
    if kind == "run_end":
        return "Run Complete"
    role = payload.get("agent_role") or ""
    step_type = payload.get("step_type") or "step"
    prefix = "Subagent " if role == "subagent" else ""
    if step_type == "planning":
        return f"{prefix}Planning Step"
    if step_type == "action":
        if _final_answer_text(payload):
            return f"{prefix}Assistant Response"
        if payload.get("is_final_answer"):
            return f"{prefix}Final Answer Step"
        if payload.get("tool_calls"):
            calls = [c for c in payload.get("tool_calls", []) if isinstance(c, dict)]
            if len(calls) == 1 and calls[0].get("name"):
                return f"{prefix}Tool Call: {calls[0].get('name')}"
            return f"{prefix}Tool Call Step"
        return f"{prefix}Action Step"
    if step_type == "task":
        return "Subagent Task"
    return f"{prefix}{str(step_type).replace('_', ' ').title()} Step"


def _timestamp(value) -> str:
    if not value:
        return ""
    try:
        return time.strftime("%H:%M:%S", time.localtime(float(value)))
    except Exception:
        return ""


def _runtime_body(kind: str, payload: dict) -> str:
    if kind == "run_start":
        return _request_body(payload.get("query"), payload.get("expanded_prompt"))
    if kind == "run_end":
        status = payload.get("status")
        error = payload.get("error")
        if error:
            return f"Status: {status}\nError: {error}"
        return f"Status: {status}" if status else ""

    final_answer = _final_answer_text(payload)
    if final_answer:
        return str(final_answer)

    sections = []
    if payload.get("model_output"):
        sections.append(_section("LLM response", payload.get("model_output")))
    if payload.get("plan"):
        sections.append(_section("Plan", payload.get("plan")))
    if payload.get("task"):
        sections.append(_section("Subagent request", payload.get("task")))
    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list):
        for index, call in enumerate(tool_calls, start=1):
            if not isinstance(call, dict):
                continue
            name = call.get("name") or "tool"
            sections.append(
                _section(
                    f"Tool call {index}: {name}",
                    _format_mapping({"parameters": call.get("arguments", {})}),
                )
            )
    if payload.get("observations"):
        sections.append(_section("Tool result", payload.get("observations")))
    if payload.get("error"):
        sections.append(_section("Error", payload.get("error")))
    return "\n\n".join(section for section in sections if section)


def _request_body(query: Any, expanded: Any) -> str:
    query_text = str(query or "")
    expanded_text = str(expanded or "")
    if expanded_text and not _same_text(query_text, expanded_text):
        return f"Request:\n{query_text}\n\nExpanded request:\n{expanded_text}"
    return query_text


def _planning_body(payload: dict, parsed_plan: dict | None) -> str:
    if isinstance(parsed_plan, dict):
        body = "\n\n".join(
            part for part in (
                _section("Plan", parsed_plan.get("text")),
                _section("Status", parsed_plan.get("status")),
            )
            if part
        )
        if body.strip():
            return body
    if payload.get("plan"):
        return _section("Plan", payload.get("plan"))
    return _section("LLM response", payload.get("model_output"))


def _final_answer_text(payload: dict) -> str | None:
    calls = payload.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        return None
    call = calls[0]
    if not isinstance(call, dict) or call.get("name") != "final_answer":
        return None
    args = call.get("arguments")
    if isinstance(args, dict) and args.get("answer") is not None:
        return str(args.get("answer"))
    return None


def _payload_at(log: list, index: int, kind: str) -> Any:
    if index < 0 or index >= len(log):
        return None
    item = log[index]
    if getattr(item, "kind", None) != kind:
        return None
    return getattr(item, "payload", None)


def _same_text(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    return str(left).strip() == str(right).strip()


def _section(title: str, value: Any) -> str:
    if value is None or value == "":
        return ""
    return f"{title}:\n{_format_value(value)}"


def _step_tokens(payload: Any) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return 0, 0
    tokens = payload.get("token_usage")
    if isinstance(tokens, dict):
        return (
            int(tokens.get("input_tokens", 0) or 0),
            int(tokens.get("output_tokens", 0) or 0),
        )
    return 0, 0


def _step_seconds(kind: str, payload: Any) -> float:
    if not isinstance(payload, dict):
        return 0.0
    timing = payload.get("timing")
    if isinstance(timing, dict) and timing.get("duration") is not None:
        return float(timing.get("duration") or 0.0)
    if kind == "run_end" and payload.get("elapsed_seconds") is not None:
        return float(payload.get("elapsed_seconds") or 0.0)
    return 0.0


def _format_tokens(input_tokens: int, output_tokens: int) -> str:
    if input_tokens == 0 and output_tokens == 0:
        return "-"
    return f"{input_tokens} in / {output_tokens} out"


def _format_seconds(seconds: float) -> str:
    if not seconds:
        return "-"
    return f"{seconds:.2f}s"


def _format_mapping(mapping: dict) -> str:
    lines = []
    for key, value in mapping.items():
        lines.append(f"{key}: {_format_value(value, indent=2)}")
    return "\n".join(lines)


def _format_value(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "\n" + "\n".join(
            f"{prefix}{key}: {_format_value(val, indent + 2)}"
            for key, val in value.items()
        )
    if isinstance(value, list):
        if not value:
            return "[]"
        return "\n" + "\n".join(
            f"{prefix}- {_format_value(item, indent + 2)}"
            for item in value
        )
    if value is None:
        return ""
    return str(value)
