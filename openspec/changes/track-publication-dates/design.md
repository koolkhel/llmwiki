## Context

See proposal.md for motivation. Current state:
- `fetch.extract()` sets `published` from mcmetadata's `publication_date` (htmldate), a naive `datetime` at midnight rendered with `.isoformat()`. There is no `modified` field and no record of where the date came from. `sources.py` writes `published` for URL and saved-page captures only.
- JSON-LD parsing already exists for authors (`_jsonld_objects`, `_types`, main-article selection inside `_jsonld_authors`).
- `pages.Page` exposes no date. `links.page_links()` already includes wikilinks in frontmatter values, so `authors: ["[[X]]"]` and `sources: ["[[S]]"]` count as links to X and S.
- `search.search()` has relevance ranking plus the `--author` filter, and no date awareness.
- `sources.missing_authors_report()` backs `source-meta --all`.

Spike on https://rossaprimavera.ru/article/c42539c8 (fetched to scratch, read-only):
- JSON-LD `NewsArticle` gives `datePublished: 2026-04-09T06:25+03:00` and `dateModified: 2026-04-14T01:00+03:00`.
- `<time datetime="2026-04-09T06:25+03:00">9 апреля 2026`, and `data-ts=1775705140`, which is 2026-04-09T03:25:40Z (the same instant).
- No `article:published_time` meta tag.
- The current capture gives `published=2026-04-09T00:00:00`: the day is right, but the time and timezone are lost and the modification isn't recorded. Authors: `Анатолий Янченко`.

## Goals / Non-Goals

**Goals:**
- Dates as precise and trustworthy as the source provides, with their provenance recorded.
- A chronological view of any concept or person that is deterministic and complete.
- The same "never lose it again" chain as for authors: capture, then source page, then lint, then backfill.

**Non-Goals:**
- Dating individual claims automatically (the agent writes dated claims, following the schema).
- Tracking the history of edits (only the latest `modified` is recorded).
- Calendar-aware filtering by time zone (filters work on the published calendar date as written).
- Obsidian Dataview snippets shipped in the vault (documented in the README, not generated).

## Decisions

### D1. Date sources and precedence (`fetch._dates(html, url, meta) -> (published, modified, via)`)
1. **JSON-LD:** the main article object, chosen by the same rules as for authors; the helper is refactored into `_main_article(html, url)` and shared. Its `datePublished` (falling back to `dateCreated`) and `dateModified` are used.
2. **Meta:** `article:published_time` / `article:modified_time` (with `property=` or `name=`), then `itemprop="datePublished"` / `"dateModified"` (meta or `<time>`).
3. **`<time datetime>`:** the first one inside `<article>` if present, else the first on the page (published only).
4. **Heuristic:** mcmetadata's `publication_date`. htmldate returns dates only, so it is always recorded as a plain date (`YYYY-MM-DD`), never as midnight.

The first source yielding a parseable published date wins. `modified` is taken from JSON-LD or meta regardless of which source gave `published`. `via` is `jsonld`, `meta`, `time` or `heuristic`.

### D2. Parsing and normalisation
`_parse_date(value) -> date | datetime | None`: strip the value, accept a trailing `Z` (as `+00:00`), and try `datetime.fromisoformat` (Python ≥ 3.11 accepts `2026-04-09T06:25+03:00`, fractional seconds and so on). If that fails, try `date.fromisoformat`. A bare year or month is rejected (too vague), and years outside 1900–2100 are rejected as junk. The stored form is `.isoformat(timespec="seconds")` for datetimes (the offset is kept when present; a naive time has no offset) and `YYYY-MM-DD` for dates. Values are written as YAML strings (quoted), which PyYAML's dumper does automatically for ISO timestamps. Source pages, by contrast, store a YAML date (unquoted `2026-04-09`), which Dataview sorts natively.

### D3. Capture and `.md` clips
`FetchedPage` gains `modified` and `published_via`. URL and saved-page captures write `published`, `published_via` and `modified` after `authors`, when set. `.md` captures read `published`, then `date`, from `original_frontmatter`. These may be YAML dates or strings, and are normalised with `_parse_date`, with `published_via: frontmatter`.

### D4. Backfill report
`missing_authors_report` becomes `missing_metadata_report`: for each raw file, *known* authors and published values come from what is recorded, else from what can be re-derived (re-extraction happens only if the source page lacks one of them and the raw file lacks it too). An item is listed when `missing` is non-empty. For published, the raw file's recorded value is used first; it is the weaker heuristic value for old captures, but the item then shows the re-derived value when that differs. Items have the form `{raw, source_page, missing: [...], authors, published}`. The CLI text shows `missing` per item.

### D5. Lint
`missing_published` (warning) applies when a source page's raw file has `published` but the source page's `published` is missing or empty. It mirrors `missing_authors` and reads only frontmatter.

### D6. Dates on pages, and search filters
`Page.published -> date | None` parses the frontmatter value (a YAML date or a string). Raw sources get the same via `RawSource.published`, keeping the precise value for sorting. The `--since`/`--until` bounds are parsed from `YYYY`, `YYYY-MM` or `YYYY-MM-DD` into an inclusive date range (month ends computed with `calendar.monthrange`). Invalid bounds raise `WikiError("invalid_date")` (exit 2). `--sort oldest|newest` sorts by `(published is None, published, title)`, with undated last in both directions. Results gain a `published` field. Query terms become optional when any of `--author`, `--since`, `--until` or `--sort` is given.

### D7. `wiki timeline` (new `timeline.py`)
- **Resolving the target:** the argument is matched as a title via the page uniqueness key, or as a vault path. If not found, raise `WikiError("page_not_found")`.
- **Membership:** the source pages among the targets of the page's `sources` links, plus the source pages whose `page_links()` resolve to the target. The latter covers `authors`, so person pages need no special case. `--author` reuses search's `_author_tier` matching over source pages instead.
- **Sort key:** the raw file's precise `published` (converted to UTC when it has an offset; a naive time or a date is taken as the start of that day in UTC) when its date agrees with the page's `published`, otherwise the page's date. Undated entries go last, then order by title.
- **Output:** `{"page", "entries": [{"published", "precise", "title", "link", "path", "authors", "summary", "undated"?}], "counts"}`. The text output prints one line per entry: `2026-04-09  [[Title]]  (Author, Author)  summary`.

### D8. Schema and workflows
- **`AGENTS.md`:** the frontmatter example gains `published: 2026-04-09` (source pages), and a new **Chronology** section covers the spec's four rules. The Workflows table stays the same. This section doesn't depend on the language, so it adds one rendering per language (the registry is regenerated).
- **Ingest:** step 4 copies `published` and adds a Timeline entry on each touched concept and person page.
- **Query:** "For questions about when or how views changed, run `wiki timeline <page> --json` (or `wiki search ... --since/--until --sort oldest`) and answer in chronological order, citing dates."
- **Lint:** the backfill step uses `missing` to fill in authors and/or `published`.
- **README:** the `timeline` command, the search options, and a Dataview snippet.

### D9. Verification and implementation notes (recorded during apply)
- **Real pages** (scratch vault, `wiki add-source`):
  - c42539c8 gives `published: 2026-04-09T06:25:00+03:00`, `modified: 2026-04-14T01:00:00+03:00`, `published_via: jsonld` and authors `[Анатолий Янченко]`.
  - 7c7b02cb gives `published: 2026-08-02T09:50:00+03:00`, `modified: 2026-09-12T20:25:00+03:00` (edited six weeks after publication, not visible before this change), `published_via: jsonld` and authors `[Владимир Колдин]`.
- **Chronology:** with made-up source pages copying those dates and linking a concept page, `wiki timeline "AI investment"` lists 2026-04-09 (Янченко) then 2026-08-02 (Колдин). `wiki search --since 2026-05 --raw` returns only the August article, with its precise timestamp. `wiki lint` reports no `missing_published` or `missing_authors`; the only errors are the dead links to the person pages, which I didn't create.
- **Backfill ordering:** `missing_metadata_report` prefers a *re-derived* `published` over the raw file's recorded one when the stored original allows it. Older captures recorded htmldate's weaker value. It re-derives only when the raw file has `original_file`, so `.txt` captures and raw files that already record everything never pay the extraction cost; the existing "recorded authors, no re-extraction" test still holds.
- **Search with no terms** now also works with just `--since`/`--until`/`--sort`. Candidates are filtered on frontmatter *before* their text is tokenised, so date-only searches are cheaper than term searches.
- **Timeline membership** uses `page_links()`, which includes frontmatter links, so person timelines (via `authors`) and concept timelines (via body links and the page's own `sources`) need no special cases.

## Risks / Trade-offs

- [JSON-LD dates can be wrong, e.g. set to the crawl or "last updated" time on some CMSs] → `published_via` makes the source visible. `modified` is kept separate, and the agent can correct the source page (the raw file stays as captured).
- [Timezone handling across sources] → sorting uses UTC instants when available. Filters work on calendar dates, a documented, deliberate simplification.
- [`source-meta --all` output shape changes] → only the lint workflow consumes it, and that template is updated in the same change. The item keys `raw`, `source_page` and `authors` keep their meaning.
- [Older raw files have the weaker heuristic `published`] → the backfill shows the re-derived value, and the agent puts it on the source page. Raw files are never rewritten.

## Migration Plan

No data migration. New captures get the precise dates. For existing vaults, run `wiki upgrade` (new schema and workflows) and then `/wiki-lint` to backfill `published` onto source pages. `wiki timeline` works immediately on any page that has dated sources.

## Open Questions

None.
