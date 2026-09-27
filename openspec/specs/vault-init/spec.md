# vault-init Specification

## Purpose

Scaffolds a new LLM wiki vault — directory layout, Claude Code schema, slash commands and permissions — so that opening the directory in Claude Code (and Obsidian) is all that is needed to start ingesting sources.

## Requirements


### Requirement: Scaffold vault layout
`wiki init <dir>` SHALL create, inside `<dir>` (creating `<dir>` if absent): `llmwiki.toml`, `raw/`, `raw/.orig/`, `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/analyses/`, `index.md`, `log.md`, `AGENTS.md`, `CLAUDE.md`, and `.gitignore`. `llmwiki.toml` SHALL record the vault layout version.

#### Scenario: Fresh directory
- **WHEN** the user runs `wiki init ~/wikis/research` and the directory does not exist
- **THEN** the directory is created containing all listed files and directories, and `wiki status --vault ~/wikis/research` succeeds

#### Scenario: Obsidian compatibility
- **WHEN** the vault is opened in Obsidian and Obsidian creates `.obsidian/`
- **THEN** the `.gitignore` written by init already excludes workspace-state files under `.obsidian/`, and no `wiki` command treats `.obsidian/` contents as pages

### Requirement: Agent integration files
`wiki init` SHALL write the vault schema to `AGENTS.md`. The schema describes the three layers (raw, wiki, schema), page types and their folders, required frontmatter, naming and linking conventions, and step-by-step workflows for ingest, query and lint that name the `wiki` commands to call at each step. It SHALL write a `CLAUDE.md` whose only instruction is to import `AGENTS.md` (`@AGENTS.md`), so both agents follow the same schema.

For each workflow (`ingest`, `query`, `lint`), `wiki init` SHALL write a Claude Code slash command `.claude/commands/<name>.md` and a Kimi Code skill `.agents/skills/wiki-<name>/SKILL.md`. Both are generated from the same workflow text and take the user's arguments. Wherever the schema or a workflow refers to another workflow, it SHALL name it in an agent-neutral way that gives both invocations (`/<name>` in Claude Code, `/skill:wiki-<name>` in Kimi Code).

`wiki init` SHALL write a `.claude/settings.json` that allows Claude Code to run `wiki` commands without prompting. It SHALL NOT write Kimi Code permission files, because Kimi Code ignores project-level permission rules. The vault `.gitignore` SHALL ignore `.kimi-code/local.toml`.

#### Scenario: Slash commands available
- **WHEN** the user opens the vault in Claude Code after init
- **THEN** `/ingest`, `/query` and `/lint` are available as project slash commands

#### Scenario: Kimi Code skills available
- **WHEN** the user opens the vault in Kimi Code after init
- **THEN** `/skill:wiki-ingest`, `/skill:wiki-query` and `/skill:wiki-lint` are available, and each passes the user's text to the workflow as its arguments

#### Scenario: One schema for both agents
- **WHEN** `AGENTS.md` and `CLAUDE.md` are inspected after init
- **THEN** `AGENTS.md` contains the schema and `CLAUDE.md` contains the `@AGENTS.md` import and no schema content of its own

#### Scenario: Same workflow text for both agents
- **WHEN** `.claude/commands/ingest.md` and `.agents/skills/wiki-ingest/SKILL.md` are compared
- **THEN** their bodies (after the frontmatter) are identical, and the same holds for `query` and `lint`

#### Scenario: Agent-neutral workflow references
- **WHEN** the schema or any workflow body mentions another workflow
- **THEN** it gives both the Claude Code form (`/ingest`) and the Kimi Code form (`/skill:wiki-ingest`)

#### Scenario: Schema instructs immutability of raw
- **WHEN** `AGENTS.md` is inspected
- **THEN** it states that files under `raw/` must never be edited and that new sources enter only via `wiki add-source`

#### Scenario: No Kimi permission file
- **WHEN** init completes
- **THEN** no file under `.kimi-code/` has been written, and `.gitignore` contains `.kimi-code/local.toml`

### Requirement: Never overwrite existing files
`wiki init` SHALL NOT modify any existing file. On a directory that already contains some of the scaffold files it SHALL create only the missing ones and report which were created and which were skipped.

#### Scenario: Re-running init on an evolved vault
- **WHEN** the user has edited `CLAUDE.md` and runs `wiki init` on the same vault again
- **THEN** `CLAUDE.md` is unchanged, any missing scaffold files are created, and the report lists `CLAUDE.md` as skipped

### Requirement: Git repository
`wiki init` SHALL initialise a git repository in the vault if it is not already inside one and `git` is available, unless `--no-git` is given. It SHALL NOT create commits.

#### Scenario: No git requested
- **WHEN** the user runs `wiki init <dir> --no-git`
- **THEN** no `.git` directory is created

### Requirement: CLI availability check
`wiki init` SHALL warn (without failing) when the `wiki` executable is not resolvable on `PATH`, because the generated Claude Code files invoke it by name.

#### Scenario: wiki not on PATH
- **WHEN** init is run via an absolute path to the venv's executable and `wiki` is not on `PATH`
- **THEN** init succeeds and prints a warning with a suggested fix

### Requirement: Legacy schema warning
When `wiki init` runs on a directory that already has a `CLAUDE.md` which does not import `AGENTS.md`, it SHALL leave that file unchanged, as the never-overwrite rule requires, and SHALL emit a warning. The warning explains that the schema now lives in `AGENTS.md` and that `CLAUDE.md` should be reduced to `@AGENTS.md` after merging any customisations into `AGENTS.md`.

#### Scenario: Re-init of a pre-change vault
- **WHEN** a vault created before this change (full schema in `CLAUDE.md`, no `AGENTS.md`) is re-initialised
- **THEN** `AGENTS.md` and the Kimi skills are created, `CLAUDE.md` is unchanged and reported as skipped, and a warning describes the manual migration

#### Scenario: Already migrated
- **WHEN** `CLAUDE.md` already contains `@AGENTS.md`
- **THEN** init emits no legacy-schema warning

### Requirement: Schema covers authorship
The `AGENTS.md` schema written by `wiki init` SHALL require that a source page records the source's authors, when known, as `authors: ["[[Name]]"]`, with each author linked to an entity page tagged `person` that lists their articles. It SHALL require claims to be attributed to their author, and name variants to be recorded as `aliases` on the person page. The ingest workflow SHALL include creating or updating the author pages from the raw file's `authors`, and asking the human when the raw file has none. The lint workflow SHALL include backfilling missing authors with `wiki source-meta --all`.

#### Scenario: Schema mentions authors
- **WHEN** `AGENTS.md` is inspected after init
- **THEN** it documents the `authors` field on source pages, person entity pages tagged `person`, attribution of claims, and `aliases` for name variants

#### Scenario: Workflows handle authors
- **WHEN** the rendered ingest and lint workflows are inspected
- **THEN** ingest includes the author-page step, and lint includes running `wiki source-meta --all` to backfill authors
