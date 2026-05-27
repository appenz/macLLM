# Skills

## Overview

Skills are markdown-defined prompt assets loaded from configured skill directories.

They are a separate request-expansion mechanism from tag plugins:

- skills handle user-invocable `/skill` mentions
- tag plugins handle `@...` and plugin-owned `/...` tokens after that

## Design

The skills subsystem is centered on `SkillsRegistry` in `macllm/core/skills.py`.

Its main roles are:

- load skill definitions from markdown files
- expose manual skill commands for the UI and request pipeline
- expose model-invocable skills to agents through `read_skill`

The key design choice is that skills are content, not code. New skills can be added by writing markdown files rather than by adding Python plugin classes.

## Skill Model

Each skill has:

- `name`
- `description`
- `body`
- `source`
- `disable_model_invocation`
- `user_invocable`

Skill files use frontmatter-like sections inside markdown. Multiple skills can be defined in one file.

### Visibility Flags

Two independent boolean flags control where a skill is accessible:

- `disable-model-invocation` (default `false`) -- when `true`, agents cannot see or fetch the skill
  via `read_skill`.
- `user-invocable` (default `true`) -- when `false`, the skill does not appear in `/` autocomplete
  and cannot be invoked via `/skillname`.

The four combinations:

| `user-invocable` | `disable-model-invocation` | Effect |
|---|---|---|
| true | false | Full access (default) |
| true | true | Manual-only: user can `/invoke`, agents cannot `read_skill` |
| false | false | Agent-only: agents can `read_skill`, user cannot `/invoke` |
| false | true | Hidden: neither path works (drafts / disabled skills) |

## Loading and Overrides

Skills are loaded from `skills_dirs` in runtime config.

`SkillsRegistry.reload()` reads **only**:

- any `*.md` file **directly** under each configured skills root (e.g. bundled `shortcuts.md` with several skills), and
- a file named **`SKILL.md` in each immediate subdirectory** of that root (Cursor-style packs such as `skills/my-pack/SKILL.md`).

For `SKILL.md`, the first YAML block may omit `name:`; the skill id is then the **parent folder name** (e.g. `notes-agent/SKILL.md` → skill `notes-agent`). With `--debug`, macLLM logs an **orange** warning when that fallback is used so packs without `name:` are obvious. Root-level `*.md` bundles must declare `name:` on every skill block.

Duplicate `name:` **within the same file** is an error (recorded in the registry’s parse list; that file’s skills are skipped). The same name in **different** files still follows last-loaded-wins across `skills_dirs` order.

Deeper paths (e.g. `references/*.md`, `my-pack/extra.md`) are **not** scanned for skill definitions; use `read_skill` with a `file=` path for auxiliary markdown inside a pack.

## Runtime Use

There are two runtime paths.

For manual use, `SkillsRegistry.expand_manual_invocation()` rewrites user-invocable `/skill` mentions into the skill body. A leading `/skill` invocation keeps the legacy argument behavior: the skill body is followed by an `ARGUMENTS:` section containing the rest of the prompt.

For agent use, `read_skill` in `macllm/tools/skills.py` exposes model-invocable skills. It can return the skill body (with a listing of additional files in the skill directory) or the content of a specific file within the skill directory. Agents that include `read_skill` also receive a generated skill catalog in their instructions.

## Boundary to Plugins

Skills run before tag plugins. After any `/skill` expansion, the resulting expanded prompt is passed into `UserRequest.process_tags()`.

This keeps skills focused on reusable prompt templates, while plugins remain responsible for token-level request transformation and side effects.
# Skills

Skills are reusable instruction snippets stored as Markdown files, discovered from configured directories. They are separate from tag plugins and from TOML “shortcuts” (legacy loader unused at app startup).

## Registry

`SkillsRegistry` (core/skills.py) loads from `skills_dirs` (`resolved_skills_dirs`): root-level `*.md` plus each child folder’s `SKILL.md` only; then parses YAML frontmatter blocks per file and indexes skills by `name`.

Frontmatter keys (structural): `name`, `description`, optional `disable-model-invocation` (bool, default false), optional `user-invocable` (bool, default true).

## Manual invocation (/)

If user input contains a `/skill` token matching a loaded user-invocable skill name, `expand_manual_invocation` replaces it with the skill body before tag processing. A leading `/skill` token additionally appends trailing text as `ARGUMENTS:`.

## Model invocation

`read_skill(name, file="")` (tools/skills.py) serves two purposes:

- `read_skill(name="my-skill")` — returns the skill body. If the skill directory contains additional files (references, scripts, assets), a listing is appended so the agent knows what is available.
- `read_skill(name="my-skill", file="references/workflows.md")` — returns the content of a specific file from the skill directory. Paths are relative to the skill root and validated against traversal.

The `name` parameter is required. Skill discovery (listing available skills) is handled by the harness: `MacLLMAgent.__init__` injects the catalog from `SkillsRegistry.model_catalog_text()` into the agent's system prompt.

`read_skill` honours `disable-model-invocation`.

Autocomplete / pill rendering for / uses `list_manual_commands` (skill commands plus built-ins such as /reload). Only skills with `user-invocable: true` (the default) appear in autocomplete and can be expanded via `/skillname`.

## Reload

/reload reloads merged runtime config and skill files and may trigger index refresh hooks in the app layer.
