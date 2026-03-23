# Skills

## Overview

Skills are markdown-defined prompt assets loaded from configured skill directories.

They are a separate request-expansion mechanism from tag plugins:

- skills handle leading `/skill` invocation
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

Skill files use frontmatter-like sections inside markdown. Multiple skills can be defined in one file.

## Loading and Overrides

Skills are loaded from `skills_dirs` in runtime config.

`SkillsRegistry.reload()` scans those directories recursively, parses markdown files, and stores skills by name.
If the same name appears more than once, the last loaded definition wins. This allows user-level overrides of project-provided skills.

## Runtime Use

There are two runtime paths.

For manual use, `SkillsRegistry.expand_manual_invocation()` rewrites a leading `/skill` invocation into the skill body, optionally appending an `ARGUMENTS:` section.

For agent use, `read_skill` in `macllm/tools/skills.py` exposes model-invocable skills. Agents that include `read_skill` also receive a generated skill catalog in their instructions.

## Boundary to Plugins

Skills run before tag plugins. After any leading `/skill` expansion, the resulting expanded prompt is passed into `UserRequest.process_tags()`.

This keeps skills focused on reusable prompt templates, while plugins remain responsible for token-level request transformation and side effects.
# Skills

Skills are reusable instruction snippets stored as Markdown files, discovered from configured directories. They are separate from tag plugins and from TOML “shortcuts” (legacy loader unused at app startup).

## Registry

`SkillsRegistry` (core/skills.py) scans `skills_dirs` from merged config (`resolved_skills_dirs`), parses YAML frontmatter blocks per file, and indexes skills by `name`.

Frontmatter keys (structural): `name`, `description`, optional `disable-model-invocation` (bool).

## Manual invocation (/)

If user input starts with / and matches a loaded skill name, `expand_manual_invocation` replaces the leading token with the skill body plus an ARGUMENTS: suffix when trailing text exists. Runs before tag processing.

## Model invocation

`read_skill` (tools/skills.py) returns full text for a model-invocable skill (honours `disable-model-invocation`). Empty name returns a list summary.

Autocomplete / pill rendering for / uses `list_manual_commands` (skill commands plus built-ins such as /reload).

## Reload

/reload reloads merged runtime config and skill files and may trigger index refresh hooks in the app layer.
