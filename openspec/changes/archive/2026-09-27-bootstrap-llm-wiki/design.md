## Context

Greenfield repo: only OpenSpec scaffolding exists. See proposal.md for motivation. Constraints established during exploration:

- **Claude Code is the brain; the CLI is the bookkeeper.** Synthesis (reading sources, writing and updating pages, spotting contradictions) happens in Claude Code, guided by the vault's `CLAUDE.md` and slash commands. The CLI does only deterministic work and never calls an LLM.
- **Tool and content are separate.** This repo holds only the tool. Vaults are separate private directories (each its own git repo). This repo's tests use synthetic fixtures only and never touch Joplin or any real notes.
- **Obsidian is the viewer**, so its conventions are binding: `[[wikilinks]]` resolved by basename, YAML frontmatter, and `.obsidian/` ignored.
- **Sources for now:** URLs and local `.txt`/`.md` files.
- Local environment: `python3` is 3.14 and `uv` is present. A spike confirmed that `mediacloud-metadata` 1.4.3 installs and imports on both 3.12 and 3.14.

## Goals / Non-Goals

**Goals:**
- A `wiki` CLI that Claude Code can call safely and repeatedly: JSON in and out, idempotent, and offline except for URL capture.
- A vault template (`CLAUDE.md` schema and slash commands) that encodes the ingest, query and lint workflows well enough that Claude follows them without re-explanation.
- All tricky bookkeeping rules (naming, Unicode, link resolution, dedup, index generation) are implemented once, in tested Python.

**Non-Goals:**
- No LLM or API calls from Python and no embedded agent loop.
- No embeddings or vector search; plain term search is enough for the expected scale (hundreds of pages).
- No PDF, audio or image sources yet, and no Obsidian plugin.
- No automatic commits. Claude or the human commits to the vault's git repo.
- No template upgrades for existing vaults beyond "create missing files". Merging template changes into an evolved `CLAUDE.md` is deferred.

## Decisions

### D1. Division of labour per operation

```
 /ingest <url|file>                        /query <question>          /lint
   wiki add-source X --json    [CLI]         wiki search ... [CLI]      wiki lint --json   [CLI]
   read raw file               [Claude]      read index.md   [Claude]   fix structural     [Claude]
   wiki search <terms>         [CLI]         read pages      [Claude]   semantic review:   [Claude]
   wiki new-page --type source [CLI]         answer + cite   [Claude]     contradictions,
   write summary, update       [Claude]      optionally file             stale claims, gaps
     entity/concept pages                      analysis page:          wiki index         [CLI]
     (wiki new-page for new)   [CLI]           wiki new-page  [CLI]    wiki log lint ...  [CLI]
   wiki lint --json; fix       [CLI/Claude]  wiki index      [CLI]
   wiki index                  [CLI]         wiki log query  [CLI]
   wiki log ingest "<title>"   [CLI]
```

The slash commands contain this sequence, and `CLAUDE.md` contains the conventions and page-type definitions. Keeping workflows in commands and conventions in the schema lets each evolve independently. *Alternative:* everything in `CLAUDE.md`. Rejected because it bloats every session's context with workflow steps that are only needed on demand.

### D2. Package layout and tooling
- `src/llmwiki/` package with console script `wiki`. `pyproject.toml` uses the hatchling build backend, and `requires-python >= 3.12`.
- Modules, one concern each, so every one is unit-testable without the CLI: `cli` (Typer app and output/exit-code handling), `vault` (discovery, layout and paths), `naming` (title→filename and uniqueness keys), `links` (wikilink parsing and resolution), `pages` (frontmatter read/write and page model), `sources` (capture, dedup and status), `fetch` (HTTP and extraction adapter), `lint`, `index`, `log`, `search`, and `templates/` (package data for vault scaffolding).
- **Typer** for the CLI: type-hinted, and its subcommands and help output fit a command-per-operation tool. *Alternative:* argparse (no dependency, but more boilerplate) or Click (Typer is built on it anyway).
- **PyYAML** with a ~20-line frontmatter splitter (`pages.parse`/`pages.dump`) instead of python-frontmatter: we need to distinguish *missing* from *unparseable* frontmatter for lint, and to emit a fixed key order without YAML anchors (a shared date object otherwise serialises as `&id001`). *(Changed during implementation.)*
- **pytest** with synthetic fixtures built in `tests/conftest.py`. These deliberately include NFD titles, emoji, Cyrillic, illegal characters, over-long titles, case-colliding duplicates and empty bodies. There are **no network calls in tests**: the fetch adapter is swapped for a stub that returns synthetic HTML.
- Dev setup: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`, then symlink `.venv/bin/wiki` into `~/.local/bin/` so vaults can call `wiki` by name. `uv` works equally well but is not required.

### D3. URL capture: fetch ourselves, then mcmetadata for metadata and trafilatura for the body
The spike on synthetic HTML showed:
- `mcmetadata.extract()` gives a good `normalized_url` (tracking params stripped, usable for dedup), plus `article_title`, `language`, `publication_date` and `text_extraction_method`.
- Its `text_content` can come back **with block boundaries removed** (the readability path joined a heading, a subheading and paragraphs with no separator). It also did not report the `<link rel=canonical>`.
- `trafilatura.extract(html, include_formatting=True, include_links=True)`, pinned at 1.8 by mcmetadata so it adds no new dependency, produced clean markdown with headings, paragraphs, lists and links.

The `fetch` adapter therefore:
1. Fetches the URL with `requests`, following redirects, with a timeout and a descriptive User-Agent.
2. Saves the response bytes unmodified to `raw/.orig/<same stem>.html`.
3. Calls `mcmetadata.extract(url=final_url, html_text=html)` for metadata.
4. Takes the body from trafilatura as markdown. If that returns nothing, it falls back to mcmetadata's `text_content`, and `extractor` records which one was used.
5. Parses `<link rel=canonical>` with BeautifulSoup (already a transitive dependency) for `canonical_url`.

The adapter is one small interface (`fetch(url) -> FetchedPage`), so the extractor can be replaced later without touching capture logic or tests. *Alternatives:* letting mcmetadata fetch internally (we would lose the raw HTML), or trafilatura alone (we would lose URL normalization, language and date detection).

### D4. No mutable state database; everything is derived from files
- Ingestion status is derived: a raw file is ingested when some `wiki/sources/*.md` page has `raw: <its path>` in its frontmatter. This keeps raw files immutable and needs no `state.json` that could drift out of sync.
- Dedup scans the frontmatter of `raw/*.md` for `sha256` and `normalized_url` on every `add-source`. That is O(n) over raw files, which is fine at expected scale, and a cache can be added later without changing behaviour.
- `raw_modified` lint compares the recorded `sha256` with a hash of the current body (normalized to `\n` line endings, and excluding frontmatter).

*Alternative:* an SQLite state file. Rejected because it would be a second source of truth for Obsidian users and for git.

### D5. Naming and link resolution live in one module
- `naming.title_to_filename()` implements the spec's rules. `naming.key()` returns the uniqueness key: the NFC filename stem with `str.casefold()` applied.
- Link resolution builds a map from `key` to paths over `wiki/` (and `raw/` for `[[raw/...]]`) and strips `|alias`, `#heading` and `#^block`. Code spans and fenced blocks are masked out before the wikilink regex runs.
- Filenames read from disk are NFC-normalized before comparison, because macOS APFS may return NFD.
- The 200-byte cap leaves headroom under the 255-byte filename limit of APFS and ext4 for the raw-file date prefix and hash suffix.

### D6. Page frontmatter contract
```yaml
type: concept            # source | entity | concept | analysis (must match folder)
summary: ""              # one line; feeds index.md
sources: []              # wikilinks to wiki/sources pages supporting this page
tags: []
created: 2026-09-27
updated: 2026-09-27
raw: raw/...             # source pages only
```
The page title is the filename, with no `title:` key, which avoids drift between the two. `CLAUDE.md` tells Claude to bump `updated` and add to `sources` when it touches a page. Checking that is Claude's job during `/lint`, not a CLI rule, because it needs judgement.

### D7. Generated files and determinism
- `index.md` starts with an HTML comment saying it is generated by `wiki index` and must not be edited. `init` writes the same output `wiki index` would generate for an empty vault, so a fresh vault lints clean (no `index_stale`).
- `log.md` entries use `## [YYYY-MM-DD HH:MM] op | message`, the greppable prefix format suggested in the pattern. The log is only ever opened in append mode.

### D8. Claude Code integration files
- `.claude/settings.json` allows `Bash(wiki:*)` and read/edit access within the vault. It does **not** allow writes under `raw/`: the schema forbids them, and `raw_modified` lint catches accidents.
- The slash commands take `$ARGUMENTS` and tell Claude to use `--json` for every CLI call and to stop and report if `add-source` fails, rather than falling back to WebFetch. WebFetch returns a model summary, which would violate the "faithful raw copy" principle.
- The templates are plain files under `llmwiki/templates/vault/`, copied verbatim with only `{{created}}`-style placeholders filled in, so they are easy to review and edit.

### D9. Implementation notes (recorded during apply)
- Console script is `wiki = llmwiki.cli:entrypoint`; `main(argv)` runs Typer with `standalone_mode=False` so usage errors also honour the `--json` single-document contract. Typer ≥ 0.2x vendors click, so its `UsageError` is imported from `typer._click` with a fallback.
- Dependencies pinned beyond mcmetadata: `trafilatura==1.8.0` (1.8.1 renders list items as `item\n-`) and `lxml_html_clean` (lxml ≥ 5.2 split out `lxml.html.clean`, which justext still imports).
- Extraction yielding under 40 characters (e.g. only a nav label) is treated as `extraction_failed` rather than stored.
- Template files are stored as `dot-claude/`, `dot-gitignore` in the package and installed as `.claude/`, `.gitignore`.
- `add-source` refuses files already inside `raw/` (`already_in_raw`), since their provenance cannot be recorded; raw files lacking capture frontmatter are reported by lint as `frontmatter_invalid`.
- Wikilinks in frontmatter values (e.g. `sources: ["[[X]]"]`) count as links for `dead_link` and `orphan`, matching Obsidian's property links.
- Known extractor cosmetics (seen on Wikipedia): trafilatura leaves `[edit]` links split across heading lines and decodes `&sect` in URLs; the original HTML is kept, so re-extraction remains possible.

## Risks / Trade-offs

- [mcmetadata's tightly pinned dependency tree (newspaper3k, goose3, old trafilatura, faust-cchardet) may conflict with future Python or dependency versions] → The tool has its own venv, the fetch adapter is isolated, and a smoke test imports the extractor stack. If it breaks, we can fall back to trafilatura plus `url-normalize` directly.
- [Extraction quality varies by site: paywalls, JS-rendered pages, boilerplate] → The raw HTML is always kept, so re-extraction is possible. Empty extraction fails loudly (exit 2) instead of storing junk. Clipping with Obsidian Web Clipper into a `.md` file and then running `add-source <file>` is a documented workaround.
- [Claude skips CLI steps or edits pages without `new-page`, producing badly named files] → `wiki lint` catches `bad_filename`, `frontmatter_*`, `type_folder_mismatch`, `dead_link` and `index_stale`, and `/ingest` ends with a lint pass.
- [Accidental edits to `raw/` break immutability] → Enforced by schema instructions, the settings deny rule and the `raw_modified` lint. Git history allows recovery.
- [Linear scans for dedup and search get slow at large scale] → Acceptable at hundreds to low thousands of files. Caching is an additive change later.
- [Title collisions between different real-world things, such as two people with the same name] → `duplicate_title` forces a disambiguating title (for example "Name (role)"). The schema documents this convention.
- [The command name `wiki` could clash with another tool on PATH] → The package name is `llmwiki`. If a clash appears, a second entry point `llmwiki` can be added without changing the specs' command semantics beyond the name.

## Migration Plan

Not applicable: a new tool with no existing users or data. Rollback means uninstalling the package, and vaults are plain markdown that stays usable in Obsidian without the tool.

## Open Questions

- Should the `CLAUDE.md` template include domain-specific page types beyond the four generic ones? This is deferred: users edit their vault's schema, and the four types cover the pattern's core.
- A `wiki init --upgrade-templates` merge flow for evolved vaults is deferred until the templates have stabilized through real use.
