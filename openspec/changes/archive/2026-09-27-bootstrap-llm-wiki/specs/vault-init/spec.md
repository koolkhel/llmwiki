## Purpose

Scaffolds a new LLM wiki vault — directory layout, Claude Code schema, slash commands and permissions — so that opening the directory in Claude Code (and Obsidian) is all that is needed to start ingesting sources.

## ADDED Requirements

### Requirement: Scaffold vault layout
`wiki init <dir>` SHALL create, inside `<dir>` (creating `<dir>` if absent): `llmwiki.toml`, `raw/`, `raw/.orig/`, `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/analyses/`, `index.md`, `log.md`, `CLAUDE.md`, and `.gitignore`. `llmwiki.toml` SHALL record the vault layout version.

#### Scenario: Fresh directory
- **WHEN** the user runs `wiki init ~/wikis/research` and the directory does not exist
- **THEN** the directory is created containing all listed files and directories, and `wiki status --vault ~/wikis/research` succeeds

#### Scenario: Obsidian compatibility
- **WHEN** the vault is opened in Obsidian and Obsidian creates `.obsidian/`
- **THEN** the `.gitignore` written by init already excludes workspace-state files under `.obsidian/`, and no `wiki` command treats `.obsidian/` contents as pages

### Requirement: Claude Code integration files
`wiki init` SHALL write a `CLAUDE.md` schema describing the three layers (raw, wiki, schema), page types and their folders, required frontmatter, naming and linking conventions, and step-by-step workflows for ingest, query and lint that name the `wiki` commands to call at each step. It SHALL write slash commands `.claude/commands/ingest.md`, `.claude/commands/query.md` and `.claude/commands/lint.md`, and a `.claude/settings.json` that allows Claude Code to run `wiki` commands without prompting.

#### Scenario: Slash commands available
- **WHEN** the user opens the vault in Claude Code after init
- **THEN** `/ingest`, `/query` and `/lint` are available as project slash commands

#### Scenario: Schema instructs immutability of raw
- **WHEN** `CLAUDE.md` is inspected
- **THEN** it states that files under `raw/` must never be edited and that new sources enter only via `wiki add-source`

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
