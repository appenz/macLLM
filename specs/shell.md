# Shell Tool

## Overview

The shell tool lets agents execute shell commands in a sandboxed environment.
It combines three layers of protection:

1. **Command whitelist** — a UX/trust layer that controls which executables the agent can run without human approval
2. **Directory grants** — per-conversation filesystem scoping driven by `@`-mentioned directories
3. **Kernel sandbox** — macOS `sandbox-exec` (Seatbelt) enforcement that restricts the subprocess to allowed paths regardless of what the command tries to do

## Architecture

### New Files

- `macllm/tools/shell.py` — the `run_command` smolagents tool
- `macllm/core/sandbox.py` — sandbox profile construction and `preexec_fn` factory
- `macllm/core/command_parser.py` — `bashlex`-based executable extraction from shell commands
- `macllm/ui/approval.py` — inline approval prompt rendering and keyboard handling

### Modified Files

- `macllm/core/config.py` / `MacLLMConfig` — new `[shell]` config section
- `macllm/core/chat_history.py` / `Conversation` — directory grant tracking
- `macllm/core/agent_status.py` — new `"pending"` tool-call status for approval UI
- `macllm/ui/main_text.py` — inline approval rendering and keyboard handling
- `macllm/tags/file_tag.py` — directory `@`-mention expansion (register granted dirs on conversation)
- `macllm/tools/__init__.py` — export `run_command`

## Command Whitelist

### Behavior

When the agent calls `run_command`, the tool:

1. Parses the command string with `bashlex` to produce an AST.
2. Walks the AST to extract every executable name (handles pipelines, `&&`/`||`/`;` chains, and `$(…)` substitutions).
3. Checks each executable against `allowed_commands` in config.
4. If all executables are whitelisted → run immediately.
5. If any executable is not whitelisted → pause and show an inline approval prompt.
6. If `bashlex` fails to parse (esoteric syntax) → treat as unwhitelisted and require approval.

### Approval Flow

The approval prompt renders inline in the agent status area (not a popup).
It shows the full command, highlights the unrecognized executables, and offers three keyboard-driven options:

- **[R]un once** — execute this command but don't remember the executable
- **[D]eny** — refuse execution; the tool returns an error message to the agent
- **[A]lways allow** — execute and add the new executable(s) to the persisted whitelist

The letters R, D, A are underlined/highlighted for discoverability.
Single keypress triggers the action (no Enter required).

After the user chooses, the multi-line approval prompt collapses:

- Run / Always Allow → single line: `✓ Shell: <command>`
- Always Allow → two lines: `✓ Shell: <command>` / `  <exe> added to allowlist`
- Deny → single line: `✗ Shell: <command> — denied`

### Configuration

```toml
[shell]
allowed_commands = [
  "ls", "cat", "head", "tail", "wc", "grep", "find",
  "sort", "uniq", "diff", "echo", "printf",
  "mkdir", "cp", "mv", "rm", "touch", "chmod",
  "git", "python", "python3",
]
```

The whitelist is stored in user config (`~/.config/macllm/config.toml`).
"Always allow" appends to this file.
Project-level config can also define allowed commands; the two lists merge.

## Directory Grants

### How Directories Are Granted

The sandbox allows read-write access only to explicitly granted directories.
There are two sources of grants:

1. **Config defaults** — `[shell] default_dirs` in `config.toml` (empty by default)
2. **Conversation `@`-mentions** — when the user references a directory with `@~/some/path/`, the file tag plugin registers it as a granted directory on the conversation

Directory grants are tracked on `Conversation` as a `granted_dirs: list[str]` field.

When `run_command` executes, it collects all granted directories from the conversation and passes them to the sandbox profile builder.

### Directory Shortcuts

For convenience, the file tag plugin recognizes shortcut prefixes:

- `@home` → `~/`
- `@desktop` → `~/Desktop/`
- `@downloads` → `~/Downloads/`
- `@documents` → `~/Documents/`

These expand like any other `@` directory mention and grant access to the corresponding path.

### Sandbox Profile (Read-Only System Paths)

Every command gets read-only access to system paths required for execution:

```
/bin, /usr/bin, /usr/sbin, /sbin           — system binaries
/usr/lib, /usr/local/lib                    — shared libraries
/usr/local/bin, /usr/local/sbin             — user-installed binaries
/opt/homebrew                               — Homebrew (Apple Silicon)
/Library, /System/Library                   — macOS frameworks
/private/etc, /private/var/db, /private/tmp — system config, temp
/etc, /tmp, /var                            — standard paths
/dev                                        — device files
```

Read-write access to `/tmp` and `/private/tmp` is always granted (commands need temp files).

### Denied Paths (Hardcoded, Non-Configurable)

These are always denied, even if a broader rule would match:

```
~/.ssh
~/.aws
~/.gnupg
~/.credentials
~/.config/macllm    (prevent the agent from modifying its own config)
```

### Tool-Friendly Read-Only Paths

Common tool config is allowed read-only by default so commands like `git` work:

```
~/.gitconfig
~/.config/git/
```

This list is configurable via `[shell] read_only_paths` in config.

## Directory Approval

When the agent runs a command that references paths outside the current grant set
(e.g. `ls ~` when `~` hasn't been mentioned with `@`), the tool detects the
ungranted paths and shows an inline approval prompt — similar to the executable
approval but for directories:

```
┌ Shell: ls ~
│ ⚠ Needs access to: ~/
│ [R]un (grant & run)  [D]eny
```

If the user presses **R**, the directories are added to the conversation's grant
list and the command runs.  If both an unknown executable and ungranted paths are
present, they are shown together in one combined prompt.

Path extraction uses `bashlex` to walk the AST and collect word arguments that
look like filesystem paths (`/…`, `~/…`, `./…`, `../…`), skipping the executable
itself (the first word of each command).

## Sandbox Enforcement

### Implementation

The sandbox uses macOS `sandbox-exec -p <profile> /bin/sh -c <command>` to
apply a Seatbelt profile before the shell even starts.  This is thread-safe
(no `preexec_fn` in multi-threaded Python) and is how Agent Safehouse and
similar tools implement sandboxing.

The sandbox profile is constructed dynamically per-command from the granted directory list.
It follows a deny-by-default model:

```scheme
(version 1)
(deny default)
(import "bsd.sb")

; system binaries and libraries (read-only)
(allow file-read* process-exec
  (subpath "/bin") (subpath "/usr/bin") ...)

; granted project directories (read-write)
(allow file-read* file-write*
  (subpath "/Users/me/projects/foo"))

; temp (read-write)
(allow file-read* file-write*
  (subpath "/private/tmp"))

; denied sensitive paths (explicit deny overrides any allow)
(deny file-read* file-write*
  (subpath "/Users/me/.ssh"))
```

Child processes inherit the sandbox and cannot escape it.

### Command Execution

Commands run via `subprocess.run(["sandbox-exec", "-p", profile, "/bin/sh", "-c", cmd], ...)`.

`shell=True`-style execution is used because:
- Agents produce natural shell syntax (pipes, redirections, variable expansion)
- The kernel sandbox is the security boundary, not shell feature restrictions
- `bashlex` parses the command for whitelist checking before execution

The tool returns stdout, stderr, and exit code to the agent.

## Output Display

Command output renders in the agent status area as an expandable block.

- By default, the first 3 lines of output are shown.
- Clicking the block expands it to show the full output.
- This matches the existing tool-call rendering pattern but adds expand/collapse behavior.

## Working Directory

The `run_command` tool accepts an optional `working_directory` parameter.
It defaults to the first granted directory on the conversation (or `/tmp` if none are granted).

The working directory must be inside a granted directory, otherwise the tool returns an error.
