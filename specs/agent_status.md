# Agent Status Display

## Overview

During a run, macLLM shows the supervising agent's plan, semantic activity updates,
the current operation, and pending shell approvals. Core records raw runtime facts;
the passive UI interprets and renders them.

## Data Sources

The UI may read both `agent.memory.steps` and `Conversation.conversation_log`.
Core does not build a UI status model.

Durable `step` facts contain raw projections of smolagents `PlanningStep`,
`ActionStep`, and `TaskStep` objects for debug/runtime history. A planning fact's
`model_output` includes the model's complete response; only the UI parses its
`<update>…</update>` tag. Existing `plan` entries provide the checklist.

Two payload-minimal, transient markers expose boundaries before work starts:

- `planning_started`, whose payload is the emitting agent's stable name
- `action_started`, whose payload is the emitting agent's stable name

Transient `tool_call` entries expose live tool use. The pre-invocation task fact
written by `LazyManagedMacLLMAgent` exposes delegation before the managed agent
runs. ConversationLog insertion order is authoritative.

Markers and tool-call entries are excluded from persistence and cleared at run
reset, completion, or interruption. Durable step, plan, token, and run logging is
unchanged.

## Rendering

`MainTextHandler` renders the active block in this order:

1. the active run's plan
2. persistent supervising-agent updates, in action order
3. one ephemeral current operation
4. pending approval UI

The UI applies these transitions:

- supervising planning starts → `Planning...`
- planning completes → the parsed `<update>` replaces `Planning...`
- the next supervising action starts → that update becomes persistent
- a supervising tool starts or reports progress → its message becomes ephemeral
- a managed agent starts → `Invoking <name> subagent...` becomes ephemeral
- a managed agent uses a tool → its tool message becomes ephemeral

Each newer ephemeral operation replaces the previous one. Persistent updates remain,
and subsequent promoted updates are added below them. Managed agents never emit or
promote `<update>` text. Missing or malformed tags produce no fallback update.

The regular UI has no Status section or historical Steps list. The complete activity
block is hidden when the run ends or is interrupted.

## Responsibilities

Core appends raw facts and sends the existing generic repaint notification. It does
not parse `<update>`, classify parent versus managed events, promote updates, choose
the visible operation, or generate display wording.

The UI identifies supervising events by comparing the marker's agent name with the
conversation agent's name. It owns tag parsing, event reduction, labels, colors, and
tool formatting. The separate debug window continues to render durable chronological
runtime facts.

`Conversation.pending_approval` remains transient conversation state. A shell tool
sets it and requests a repaint; the UI renders it after agent activity until the user
decides.
