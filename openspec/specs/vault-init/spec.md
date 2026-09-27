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

### Requirement: Upgrade vault templates
`wiki upgrade` SHALL bring an existing vault's template-managed files up to date. These are the files `wiki init` renders from templates, except `llmwiki.toml` and `log.md`. It uses a registry, shipped with the tool, of the content hashes of every version of every template-managed file the tool has ever produced, including paths it no longer produces (**obsolete paths**). Hashes are computed after normalising line endings to `\n`. For each file:
- a current path that is missing SHALL be created;
- a current path whose content equals the current template SHALL be left unchanged;
- a current path whose content equals any older known version SHALL be replaced with the current template;
- a current path whose content matches no known version (the user edited it) SHALL be left unchanged, and the current template SHALL be written to `<path>.new` (replacing any earlier `.new`) and reported as a conflict;
- an obsolete path whose content matches a known version SHALL be deleted;
- an obsolete path whose content matches no known version SHALL be kept and reported with a warning naming the path that replaces it.

`wiki upgrade` SHALL NOT read or modify `raw/`, `wiki/`, `index.md` or `log.md`, and SHALL NOT modify `llmwiki.toml`; it SHALL read `llmwiki.toml` only to obtain the vault's `language`, which selects the current rendering of `AGENTS.md`. The registry SHALL cover the renderings of every template-managed file for every supported language and for the unset language. `--dry-run` SHALL report the same plan and write nothing. The report SHALL list each file with its action (`created`, `updated`, `unchanged`, `conflict`, `deleted`, `kept`), and with `--json` it SHALL be one JSON document. If the vault is a git repository with uncommitted changes to any template-managed file, the command SHALL warn and suggest committing first, but still proceed. Running `wiki upgrade` again with no template changes SHALL change nothing, apart from rewriting an identical `.new` for files that are still in conflict.

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

#### Scenario: Switching the wiki language
- **WHEN** a vault with an untouched `AGENTS.md` and no `language` gets `language = "en"` added to `llmwiki.toml` and `wiki upgrade` runs
- **THEN** `AGENTS.md` is updated to the English-language rendering, and `llmwiki.toml` is byte-identical afterwards

#### Scenario: Untouched rendering for another language
- **WHEN** a vault initialised with `--language ru` has an untouched `AGENTS.md`
- **THEN** `wiki upgrade` reports it `unchanged`, not `conflict`

### Requirement: Wiki language
A vault MAY declare its wiki language in `llmwiki.toml` as `language = "<code>"`, where `<code>` is one of the supported codes (at least `en`, `ru`, `zh`, `hi`, `de`, `fr`, `es`). `wiki init --language <code>` SHALL write it. An unsupported code SHALL be rejected as a usage error listing the supported codes. Commands that read the setting SHALL treat an unknown or malformed value the same way.

When `language` is set, the `AGENTS.md` written by `init` (and by `upgrade`) SHALL contain a "Language" section, naming the language, which requires that:
- page titles and prose are written in the wiki language, and raw sources are never translated or modified;
- each concept's names in other languages and scripts are recorded under the page's `aliases:`;
- quotations keep the original text, followed by a translation into the wiki language;
- people get their established name in the wiki language as the page title, with the original-script name as an alias;
- source pages record the source's `language` from the raw file.

When `language` is not set, the schema SHALL keep the instruction to write in the language of the source.

#### Scenario: English vault
- **WHEN** the user runs `wiki init ~/wikis/ai --language en`
- **THEN** `llmwiki.toml` contains `language = "en"`, and `AGENTS.md` has a Language section requiring English titles and prose, multilingual `aliases`, original-plus-translation quotes, and `language` on source pages

#### Scenario: Unsupported language
- **WHEN** the user runs `wiki init v --language xx`
- **THEN** the command exits with code 2, lists the supported codes, and creates nothing

#### Scenario: No language set
- **WHEN** a vault is initialised without `--language`
- **THEN** `llmwiki.toml` has no `language` key and `AGENTS.md` says to write in the language of the source

### Requirement: Schema covers chronology
The `AGENTS.md` schema written by `wiki init` SHALL contain a Chronology section requiring that:
- source pages record `published` (the date) copied from the raw file, when known;
- claims on concept and person pages state when and by whom they were made (e.g. "In April 2026, [[Author]] argued … ([[Source]])");
- concept and person pages keep a **Timeline** section of dated entries in chronological order, one per source;
- questions about change over time are answered using `wiki timeline`.

The ingest workflow SHALL include copying `published` and adding a Timeline entry. The query workflow SHALL direct time-related questions to `wiki timeline` and `--since`/`--until`/`--sort`. The lint workflow's backfill step SHALL fill in both authors and dates from `wiki source-meta --all`.

#### Scenario: Schema mentions chronology
- **WHEN** `AGENTS.md` is inspected after init
- **THEN** it documents `published` on source pages, dated claims, Timeline sections and `wiki timeline`

#### Scenario: Workflows handle dates
- **WHEN** the rendered ingest, query and lint workflows are inspected
- **THEN** ingest copies `published` and adds a Timeline entry, query mentions `wiki timeline`, and lint backfills `published`
