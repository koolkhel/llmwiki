## MODIFIED Requirements

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

## ADDED Requirements

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
