## 1. Project setup

- [x] 1.1 Create `pyproject.toml` (hatchling, `requires-python >= 3.12`, console script `wiki = llmwiki.cli:entrypoint`, deps: typer, pyyaml, requests, beautifulsoup4, mediacloud-metadata, trafilatura==1.8.0, lxml_html_clean; dev extra: pytest), `src/llmwiki/__init__.py`, `tests/`, `.gitignore` (incl. `.venv/`), and a README with venv setup and the `~/.local/bin/wiki` symlink step; verify `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'` succeeds and `.venv/bin/wiki --help` runs
- [x] 1.2 Add `tests/conftest.py` with a `tmp_vault` fixture and a synthetic-title corpus (NFD accents, emoji, Cyrillic, illegal chars, >200-byte titles, case-colliding duplicates, empty bodies) — no real note content; verify `pytest` collects and runs a trivial test
- [x] 1.3 Add an extractor smoke test that imports `mcmetadata` and `trafilatura` and extracts a synthetic HTML string offline; verify it passes on the venv's Python

## 2. CLI conventions and vault discovery

- [x] 2.1 Implement `vault` module: discovery order `--vault` → `LLMWIKI_VAULT` → nearest ancestor with `llmwiki.toml`, plus layout path helpers; verify unit tests for each discovery path and the not-found case
- [x] 2.2 Implement the Typer app skeleton with shared `--json` / `--vault` handling, a single JSON-document stdout contract, `{error: {code, message}}` errors, and exit codes 0/1/2; verify tests that `--json` stdout parses as exactly one JSON document for success and error, and usage errors exit 2

## 3. Page naming, frontmatter and links

- [x] 3.1 Implement `naming.title_to_filename()` and `naming.key()` per the page-naming spec; verify parametrised tests for every spec scenario (illegal chars, NFD→NFC, 200-byte multibyte truncation, empty-after-sanitising rejection, emoji preserved)
- [x] 3.2 Implement `pages` module: read/parse frontmatter, write with fixed key order, page model with type↔folder mapping, NFC-normalised directory listing ignoring `.obsidian/`; verify round-trip tests and NFD-on-disk listing test
- [x] 3.3 Implement `links` module: wikilink extraction (alias, heading, block ref, path form) with code-span/fence masking, and resolution against a vault key map; verify tests for each resolution scenario and the in-code exclusion
- [x] 3.4 Implement `wiki new-page --type ... "<title>" [--raw]` with vault-wide uniqueness check, required frontmatter, `link` in output, and source-page `--raw` validation; verify CLI tests for creation, `duplicate_title` across folders, and missing/invalid `--raw`

## 4. Source capture

- [x] 4.1 Implement `fetch` adapter (`fetch(url) -> FetchedPage`): requests with timeout/redirects/User-Agent, raw bytes kept, mcmetadata metadata, trafilatura markdown body with `text_content` fallback, canonical link parsing, `extractor` recorded, typed errors for HTTP/timeout/empty extraction; verify unit tests using a stubbed HTTP layer and synthetic HTML (no network)
- [x] 4.2 Implement `sources` module: raw filename `YYYY-MM-DD-<title>.md` with hash suffix on collision, frontmatter per spec for `kind: url` and `kind: file`, `original_frontmatter` preservation, sha256 over normalised body, dedup by sha256 and normalized_url; verify unit tests for naming collision, both kinds, and both dedup paths
- [x] 4.3 Implement `wiki add-source <url|path>` wiring the above, writing `.orig` HTML, rejecting binary/non-UTF-8/directories with exit 2 and no writes, and reporting `duplicate_of`; verify CLI tests with the stub fetcher covering success, failure (nothing written), duplicate, and file capture leaving the original untouched
- [x] 4.4 Implement derived ingestion status (raw ↔ `wiki/sources/*` `raw:` field); verify a test where creating a source page flips a raw file from pending to ingested without changing its bytes

## 5. Navigation: index, log, search, status

- [x] 5.1 Implement `wiki index` (generated-notice header, fixed group order, case-insensitive sort, `- [[Title]] — summary`, summary-less entries); verify tests for content, ordering, and byte-identical re-runs
- [x] 5.2 Implement `wiki log <op> <message> [--detail]` with allowed ops and append-only writes; verify tests for format, chronological append, preserved prior content, and unknown-op rejection leaving `log.md` unchanged
- [x] 5.3 Implement `wiki search <query> [--type] [--limit] [--raw]` with all-terms, case- and accent-insensitive matching, title > summary/tags > body ranking, and snippets; verify tests for ranking, accent-insensitivity, type filter, limit, and raw mode
- [x] 5.4 Implement `wiki status` (vault path, counts per type, total/pending raw, pending list, index staleness, last log heading); verify a CLI test after a stubbed capture reports one pending source

## 6. Lint

- [x] 6.1 Implement `lint` checks: dead_link, duplicate_title, bad_filename, frontmatter_missing/invalid, type_folder_mismatch, raw_missing, raw_modified, orphan (ignoring index.md), empty_summary, index_stale, pending_source; verify one test per code using a synthetic vault that triggers exactly that finding
- [x] 6.2 Implement `wiki lint [--strict]` output (findings + per-severity counts) and exit status, read-only; verify tests for warnings-only exit 0 vs `--strict` exit 1, errors exit 1, and no files modified

## 7. Vault init and Claude Code templates

- [x] 7.1 Write vault templates under `src/llmwiki/templates/vault/`: `CLAUDE.md` schema (three layers, page types/folders, frontmatter contract, naming & `[[wikilink]]` conventions, disambiguation convention, raw immutability, "never use WebFetch for sources", commit guidance), `.claude/commands/{ingest,query,lint}.md` encoding the D1 sequences with `--json` calls, `.claude/settings.json` (allow `Bash(wiki:*)`, deny edits under `raw/`), `.gitignore` (Obsidian workspace files), `llmwiki.toml`, `log.md`; verify templates are included as package data (`pip install` non-editable into a scratch venv and list them)
- [x] 7.2 Implement `wiki init <dir> [--no-git]`: create layout, copy templates, generate initial `index.md` via the index module, create-missing-only with created/skipped report, `git init` when appropriate, PATH warning for `wiki`; verify tests for fresh init, re-init preserving an edited `CLAUDE.md`, `--no-git`, and that `wiki lint` on a fresh vault exits 0 with no errors or warnings

## 8. End-to-end verification

- [x] 8.1 Add an end-to-end test on a temp vault with the stub fetcher: init → add-source (URL and file) → new-page source/concept with links → index → log → status → lint clean; verify it passes
- [x] 8.2 Manual smoke run: `wiki init` a throwaway vault in a scratch dir, `wiki add-source` one real public URL, open the vault in Claude Code and run `/ingest` on it, then open in Obsidian and confirm links/backlinks resolve; verify `wiki lint` is clean afterwards and record any template adjustments needed
