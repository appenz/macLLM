# Skills

## Overview

Skills are predefined prompt assets stored as Markdown in configured `/skills` mounts.
They are content, not executable plugins. This is why the skills subsystem may read
configured skill files before or during an agent run: those files are part of macLLM's
prompt asset system, not dynamic user resources such as clipboard data, arbitrary files,
URLs, screenshots, or images.

The skills subsystem is separate from tag plugins:

- skills handle `/skill` manual invocation and the out-of-band agent catalog
- tag plugins handle UI/input shorthand such as `@clipboard` and plugin-owned `/...` tokens

## Registry

`SkillsRegistry` in `macllm/core/skills.py` loads skill definitions from configured filesystem
mounts under `/skills`.

It reads only:

- `*.md` files directly under each configured skills root
- `SKILL.md` in each immediate child directory of a configured skills root

Each skill has `name`, `description`, `body`, `source`, `disable_model_invocation`, and `user_invocable`.
Skill files use frontmatter-like sections inside Markdown. Multiple skills can be defined in one file.

## Visibility

Two flags control where a skill is available:

- `user-invocable` (default `true`): when true, the user can invoke the skill with `/skillname`.
- `disable-model-invocation` (default `false`): when false, the skill appears in agent catalogs.

This allows manual-only, model-only, fully available, and hidden skills.

## Runtime Paths

Skills have three distinct runtime paths:

- **Manual invocation**: `SkillsRegistry.expand_manual_invocation()` rewrites a user-entered `/skill` into the skill body before tag plugins run. A leading `/skill` also appends trailing user text as an `ARGUMENTS:` section.
- **Agent tool use**: the catalog supplies each skill's `/skills/...` path and agents load it with
  `read_file`.
- **Agent preload**: `[agents.<name>].preload_skill` appends one configured skill body to that agent's instructions when the agent is constructed. Only preload skills are baked into the system prompt automatically.

Configuring `[agents.<name>].skills` does not bake those skill bodies into the prompt. It filters
the `skills_catalog` rendered explicitly in the agent's system prompt and planning prompts.

## Boundary To Tag Plugins

Skills run before tag plugins for manual `/skill` invocation. After that, tag plugins may apply UI/input sugar to remaining `@...` and plugin-owned `/...` tokens.

Skills may read configured prompt asset files. Tag plugins do not read or marshal dynamic external resources.

## Reload

`/reload` reloads merged runtime config and skill files and may trigger index refresh hooks in the app layer.
