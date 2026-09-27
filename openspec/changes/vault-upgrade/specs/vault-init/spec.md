## MODIFIED Requirements

### Requirement: Agent integration files
`wiki init` SHALL write the vault schema to `AGENTS.md`. The schema describes the three layers (raw, wiki, schema), page types and their folders, required frontmatter, naming and linking conventions, and step-by-step workflows for ingest, query, lint and upgrade that name the `wiki` commands to call at each step. It SHALL write a `CLAUDE.md` whose only instruction is to import `AGENTS.md` (`@AGENTS.md`), so both agents follow the same schema.

For each workflow (`ingest`, `query`, `lint`, `upgrade`), `wiki init` SHALL write a Claude Code slash command `.claude/commands/wiki-<name>.md` and a Kimi Code skill `.agents/skills/wiki-<name>/SKILL.md`. Both are generated from the same workflow text and take the user's arguments. Wherever the schema or a workflow refers to another workflow, it SHALL name it in an agent-neutral way that gives both invocations (`/wiki-<name>` in Claude Code, `/skill:wiki-<name>` in Kimi Code), and it SHALL NOT use the unprefixed forms `/ingest`, `/query`, `/lint` or `/upgrade`.

`wiki init` SHALL write a `.claude/settings.json` that allows Claude Code to run `wiki` commands without prompting. It SHALL NOT write Kimi Code permission files, because Kimi Code ignores project-level permission rules. The vault `.gitignore` SHALL ignore `.kimi-code/local.toml`.

#### Scenario: Slash commands available
- **WHEN** the user opens the vault in Claude Code after init
- **THEN** `/wiki-ingest`, `/wiki-query`, `/wiki-lint` and `/wiki-upgrade` are available as project slash commands

#### Scenario: Kimi Code skills available
- **WHEN** the user opens the vault in Kimi Code after init
- **THEN** `/skill:wiki-ingest`, `/skill:wiki-query`, `/skill:wiki-lint` and `/skill:wiki-upgrade` are available, and each passes the user's text to the workflow as its arguments

#### Scenario: One schema for both agents
- **WHEN** `AGENTS.md` and `CLAUDE.md` are inspected after init
- **THEN** `AGENTS.md` contains the schema and `CLAUDE.md` contains the `@AGENTS.md` import and no schema content of its own

#### Scenario: Same workflow text for both agents
- **WHEN** `.claude/commands/wiki-ingest.md` and `.agents/skills/wiki-ingest/SKILL.md` are compared
- **THEN** their bodies (after the frontmatter) are identical, and the same holds for `query`, `lint` and `upgrade`

#### Scenario: Agent-neutral workflow references
- **WHEN** the schema or any workflow body mentions another workflow
- **THEN** it gives both the Claude Code form (`/wiki-ingest`) and the Kimi Code form (`/skill:wiki-ingest`), and no unprefixed `/ingest`-style form appears

#### Scenario: Schema instructs immutability of raw
- **WHEN** `AGENTS.md` is inspected
- **THEN** it states that files under `raw/` must never be edited and that new sources enter only via `wiki add-source`

#### Scenario: No Kimi permission file
- **WHEN** init completes
- **THEN** no file under `.kimi-code/` has been written, and `.gitignore` contains `.kimi-code/local.toml`

## ADDED Requirements

### Requirement: Upgrade vault templates
`wiki upgrade` SHALL bring an existing vault's template-managed files up to date. These are the files `wiki init` renders from templates, except `llmwiki.toml` and `log.md`. It uses a registry, shipped with the tool, of the content hashes of every version of every template-managed file the tool has ever produced, including paths it no longer produces (**obsolete paths**). Hashes are computed after normalising line endings to `\n`. For each file:
- a current path that is missing SHALL be created;
- a current path whose content equals the current template SHALL be left unchanged;
- a current path whose content equals any older known version SHALL be replaced with the current template;
- a current path whose content matches no known version (the user edited it) SHALL be left unchanged, and the current template SHALL be written to `<path>.new` (replacing any earlier `.new`) and reported as a conflict;
- an obsolete path whose content matches a known version SHALL be deleted;
- an obsolete path whose content matches no known version SHALL be kept and reported with a warning naming the path that replaces it.

`wiki upgrade` SHALL NOT read or modify `raw/`, `wiki/`, `index.md`, `log.md` or `llmwiki.toml`. `--dry-run` SHALL report the same plan and write nothing. The report SHALL list each file with its action (`created`, `updated`, `unchanged`, `conflict`, `deleted`, `kept`), and with `--json` it SHALL be one JSON document. If the vault is a git repository with uncommitted changes to any template-managed file, the command SHALL warn and suggest committing first, but still proceed. Running `wiki upgrade` again with no template changes SHALL change nothing, apart from rewriting an identical `.new` for files that are still in conflict.

#### Scenario: Untouched vault from an older version
- **WHEN** a vault created by the first release (full schema in `CLAUDE.md`, commands `.claude/commands/{ingest,query,lint}.md`) is upgraded without edits
- **THEN** `AGENTS.md`, the four `wiki-*` commands and skills are created; `CLAUDE.md` is replaced with the `@AGENTS.md` stub; and the old `ingest.md`, `query.md` and `lint.md` are deleted

#### Scenario: Edited AGENTS.md
- **WHEN** the user has customised `AGENTS.md` and runs `wiki upgrade`
- **THEN** `AGENTS.md` is unchanged, `AGENTS.md.new` holds the current template, and the report lists `AGENTS.md` as a conflict

#### Scenario: Edited obsolete command
- **WHEN** the user edited `.claude/commands/ingest.md` in an older vault
- **THEN** the file is kept, `.claude/commands/wiki-ingest.md` is created, and a warning says the edits should be merged into `wiki-ingest.md`

#### Scenario: Dry run
- **WHEN** `wiki upgrade --dry-run` runs on an outdated vault
- **THEN** the report shows the planned actions and every file in the vault is byte-identical afterwards

#### Scenario: Content untouched
- **WHEN** `wiki upgrade` runs on any vault
- **THEN** every file under `raw/` and `wiki/`, plus `index.md`, `log.md` and `llmwiki.toml`, is byte-identical afterwards

#### Scenario: Idempotent
- **WHEN** `wiki upgrade` runs twice in a row
- **THEN** the second run reports only `unchanged` and `conflict` entries and modifies no user file

#### Scenario: Uncommitted changes
- **WHEN** the vault is a git repository with an uncommitted edit to `AGENTS.md`
- **THEN** the upgrade proceeds and the output includes a warning suggesting a commit first
