## Why

Vaults created by `wiki init` only work with Claude Code: the schema lives in `CLAUDE.md` and the workflows are `.claude/commands/*.md`. Kimi Code reads neither. A live probe with Kimi Code 2.1.1 confirmed that it loads `AGENTS.md`, discovers skills in `.agents/skills/` with `$ARGUMENTS` support, ignores permission rules in the project-level `.kimi-code/local.toml`, and, in Ask When Needed mode, refused to edit `raw/` because `AGENTS.md` says not to. The `wiki` CLI is already agent-neutral; only the vault's instruction files need to change for both agents to work on the same vault.

## What Changes

- The vault schema moves to **`AGENTS.md`**, the single source. `CLAUDE.md` becomes a one-line import (`@AGENTS.md`), so Claude Code sees the same schema.
- The ingest, query and lint workflows are written from **one template per workflow** into both `.claude/commands/<name>.md` (Claude Code: `/ingest`, `/query`, `/lint`) and `.agents/skills/wiki-<name>/SKILL.md` (Kimi Code: `/skill:wiki-ingest`, …). The workflow text is identical for both agents.
- Instructions name workflows neutrally, e.g. "the **ingest** workflow (`/ingest` in Claude Code, `/skill:wiki-ingest` in Kimi Code)", instead of Claude-only slash commands.
- No Kimi permission file is written, because project-level rules are ignored. The README documents how `raw/` is protected under each agent and approval mode, with `wiki lint` (`raw_modified`) and git as the backstop.
- The vault `.gitignore` also ignores `.kimi-code/local.toml`, which holds machine-specific paths.
- `wiki init` warns when an existing vault still has a full `CLAUDE.md` schema, which would then duplicate the new `AGENTS.md`, and explains the manual migration.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `vault-init`: the "Claude Code integration files" requirement is renamed to "Agent integration files" and rewritten to cover `AGENTS.md` as the schema, the `CLAUDE.md` import, Kimi Code skills, agent-neutral workflow naming, the `.gitignore` entry and the migration warning.

## Impact

- Code: `scaffold.py` (rendering one workflow template into two file formats, plus the migration warning), the vault templates, the README and `tests/test_init.py`.
- No CLI behaviour changes outside `wiki init`, and no new dependencies.
- Existing vaults: rerunning `wiki init` adds `AGENTS.md` and the Kimi skills but, as always, never modifies an existing `CLAUDE.md`. The user merges it by hand, as the warning explains.
