# Tasks

## Overview

Tasks allow macLLM to run as a headless task runner for complex LLM-driven work.
A task is submitted via the `-task <filename>` CLI option. The file uses the same
frontmatter format as skills, with additional task-specific properties for budgets
and logging.

In task mode macLLM runs without a UI, executes the task autonomously (no user
interaction), writes the result to stdout (or a logfile), and exits.

## Task File Format

Task files are markdown with optional `---` frontmatter, identical to skill files:

```markdown
---
name: competitor-research
description: Research competitor pricing
token-budget: 50000
time-budget: 600
logfile: ~/logs/research.log
---
Find the current pricing for the top 3 competitors in the
widget market and summarize in a table.
```

### Frontmatter Properties

| Property | Type | Default | Description |
|---|---|---|---|
| `name` | string | filename stem | Identifier for logging |
| `description` | string | `""` | Human-readable description |
| `token-budget` | int | `100000` | Max total tokens before tool use is disabled |
| `time-budget` | int (seconds) | `1800` | Max elapsed seconds before tool use is disabled |
| `logfile` | path | none (stdout) | Output destination; `--debug` output also routed here |

All properties are optional. A task file with no frontmatter is just the task body.

Skill-only properties (`disable-model-invocation`, `user-invocable`) are parsed
but ignored when the file is used as a task. Task-only properties are parsed but
ignored when a file is used as a skill.

## CLI Interface

```
python -m macllm -task <filename> [options]
```

### Task-specific options

| Flag | Description | Overrides |
|---|---|---|
| `--token-budget N` | Max tokens | `token-budget` in file |
| `--time-budget N` | Max seconds | `time-budget` in file |
| `--logfile PATH` | Output file | `logfile` in file |
| `--debug` | Debug output to stderr (or logfile) | — |

CLI flags override task file values. Task file values override defaults.

## Execution Model

### Headless Init

When `-task` is provided, macLLM starts in headless mode:

- No UI window is created (`MacLLMUI` is not instantiated)
- No hotkey registration
- A single ephemeral conversation is created
- The task body is submitted to the conversation
- The process blocks until the agent completes, then exits

### Agent Behaviour

The agent receives a modified system prompt that instructs it to work
autonomously:

- Do NOT ask the user for clarification (no user is present)
- Make reasonable assumptions and proceed
- Use as many tool calls as needed (no "limit to 3 calls" constraint)
- If a tool fails, try alternatives before giving up

This replaces the default interactive prompt which encourages asking for
clarification.

### Budget Enforcement

Both budgets act as soft limits — when exceeded, tool use is disabled and the
agent is interrupted to produce a final answer.

**Token budget:** After each agent step, the step callback checks cumulative
token usage (`conversation.usage.input_tokens + output_tokens`). If the budget
is exceeded, the agent is interrupted.

**Time budget:** After each agent step, elapsed wall-clock time since the run
started is checked. If exceeded, the agent is interrupted.

When interrupted by budget:
1. `agent.interrupt_switch` is set (same mechanism as user abort)
2. The agent produces a final answer with tools disabled
3. The output includes a note that the budget was exceeded
4. Exit code is still `0` (budget exhaustion is a normal completion)

### Output

- **No logfile (default):** Final answer is written to stdout. Debug output
  (with `--debug`) goes to stderr.
- **With logfile:** Final answer and debug output are written to the logfile.
  Nothing is written to stdout.

### Exit Codes

- `0` — Normal completion (including budget-exhausted completions)
- `1` — Error (file not found, API failure, missing API key, etc.)

## Implementation

### Key Files

- `macllm/core/task_runner.py` — `TaskDefinition` dataclass, file parsing,
  `run_task()` headless execution loop
- `macllm/macllm.py` — CLI argument parsing, headless branch in `main()`
- `macllm/agents/base.py` — `task_mode` flag for prompt switching
- `macllm/agents/prompts/default.yaml` — task-mode prompt text
- `macllm/core/agent_service.py` — budget-aware step callback

### Parsing

Task file parsing reuses `_parse_frontmatter` and `_FRONTMATTER_RE` from
`macllm/core/skills.py`. The first `---` block is parsed for properties; the
body is everything after the closing `---`.

### Relationship to Skills

Tasks and skills share the same frontmatter format. The parser is shared. Each
consumer ignores properties that don't apply:

- Skills ignore `token-budget`, `time-budget`, `logfile`
- Tasks ignore `disable-model-invocation`, `user-invocable`

A single `.md` file could serve as both a skill and a task, though in practice
they serve different purposes.

## Tests

**Offline** (`make test`, marker: none — included in default suite):
- Task file parsing (all properties, no frontmatter, partial, defaults)
- CLI override precedence
- Budget enforcement (mock step callback)
- Task-mode system prompt content
- Logfile routing

**External** (`make test-external`, marker: `external`):
- End-to-end task execution with real LLM
- Budget enforcement with low token budget
