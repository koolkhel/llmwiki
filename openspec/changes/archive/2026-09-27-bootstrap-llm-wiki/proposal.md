## Why

Karpathy's "LLM Wiki" pattern (an LLM incrementally maintaining a persistent, cross-linked markdown wiki synthesised from curated raw sources) needs two things to work in practice: an LLM that does the synthesis, and reliable bookkeeping that LLMs are bad at (link integrity, indexes, dedup, logs). Claude Code can already do the synthesis; what is missing is a small, deterministic, testable Python CLI it can drive, plus a vault layout and schema that tell Claude how to behave as a disciplined wiki maintainer. Nothing exists yet — this repo is greenfield.

## What Changes

- New Python package (installed into a venv) providing a `wiki` CLI. Every command is deterministic, needs no LLM or API key, and offers machine-readable JSON output so Claude Code can call it.
- `wiki init <dir>` scaffolds a **vault** separate from this repo: `raw/`, `wiki/{sources,entities,concepts,analyses}/`, `index.md`, `log.md`, a `CLAUDE.md` schema, Claude Code slash commands (`/ingest`, `/query`, `/lint`), and a permissions allowlist for the `wiki` commands.
- `wiki add-source <url|file>` captures a URL (fetched and extracted with the Media Cloud `mediacloud-metadata` extractor) or a local text/markdown file into immutable `raw/`, with provenance frontmatter, original HTML preserved, and duplicate detection.
- `wiki new-page` creates wiki pages whose filename is the page title (Obsidian-native `[[wikilinks]]`), with the CLI owning all filename sanitisation, Unicode NFC normalisation, and duplicate-title rules.
- `wiki lint` performs structural health checks (dead links, orphans, frontmatter, naming, uncovered sources); semantic checks (contradictions, stale claims) are left to Claude via `/lint`.
- `wiki index` regenerates `index.md`; `wiki log` appends to `log.md` in a greppable format; `wiki search` finds pages; `wiki status` reports vault state including sources pending ingestion.
- The vault is designed to be opened in Obsidian as the human viewer.

## Capabilities

### New Capabilities
- `cli-conventions`: Cross-cutting CLI behaviour — vault discovery, JSON output, exit codes, idempotency, no network except explicit URL capture.
- `vault-init`: Scaffolding a new vault, including the Claude Code schema, slash commands and permissions, without overwriting existing files.
- `source-capture`: Capturing URLs and local text files into immutable `raw/` with provenance, duplicate detection, and pending/ingested status.
- `page-naming`: Title-to-filename rules, page creation, and Obsidian-compatible wikilink resolution.
- `wiki-lint`: Structural health checks over the vault with a clear error/warning/info model.
- `wiki-navigation`: Generated `index.md`, append-only `log.md`, page search, and vault status reporting.

### Modified Capabilities
<!-- None: no existing specs. -->

## Impact

- New code: `pyproject.toml`, `src/llmwiki/`, `tests/`, and vault templates (CLAUDE.md schema, slash commands) shipped as package data.
- New dependencies: `mediacloud-metadata` (heavy, tightly-pinned transitive tree: trafilatura, newspaper3k, goose3, readability), a CLI framework, a YAML/frontmatter library, pytest.
- Vaults live outside this repo and are private; this repo's tests use synthetic fixtures only and never read Joplin or any real notes.
- Human workflow: install once into a venv, put `wiki` on PATH, `wiki init ~/wikis/<name>`, open that directory in Claude Code and Obsidian.
