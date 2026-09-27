## 1. Date extraction

- [x] 1.1 Refactor the main-article selection into `fetch._main_article()`, and add `_parse_date()` (D2) and `_dates()` (D1 precedence, plus `modified` and `via`). Verify with synthetic unit tests: JSON-LD with an offset; `Z` suffix; date-only meta; `<time>` inside `<article>` preferred over one elsewhere; JSON-LD beats a conflicting heuristic date; the heuristic stored as a plain date; junk and out-of-range values skipped; `dateModified` recorded even when `published` comes from meta; nothing found.
- [x] 1.2 Add `modified` and `published_via` to `FetchedPage`, and write `published`/`published_via`/`modified` in URL and saved-page captures, plus the `.md` frontmatter `published`/`date` (D3). Verify with capture tests for each kind, including a Web Clipper-style `published: 2026-03-01` and a no-date capture with none of the keys.

## 2. Backfill and lint

- [x] 2.1 Replace the report with `missing_metadata_report` (D4): the `missing` list and the known `published`, with CLI text showing `missing`. Update the existing `source-meta` tests to the new item shape. Verify with a test where the source page has authors but no date (it gets `missing: ["published"]` with the derived value) and the existing read-only snapshot test.
- [x] 2.2 Add the `missing_published` lint warning (D5). Verify with one-defect tests (present, absent when dated), and that the authored and clean fixtures stay clean.

## 3. Search filters and timeline

- [x] 3.1 Add `Page.published`/`RawSource.published` and the search `--since`/`--until`/`--sort` (D6), with optional terms and a `published` field in results. Verify with tests for each spec scenario (period filter, oldest/newest with undated last, invalid date exits 2, `--raw` filtering) and that existing search tests still pass.
- [x] 3.2 Add `timeline.py` and `wiki timeline <page> [--author] [--since] [--until] [--json]` (D7). Verify with tests for the concept, person, author-name and same-day-precision scenarios, the unknown page (exit 2), and read-only behaviour.

## 4. Templates and docs

- [x] 4.1 Add the Chronology section and the `published` frontmatter line to `AGENTS.md`, and the ingest, query and lint workflow steps (D8), and update the README (timeline, search options, a Dataview snippet). Re-run `scripts/known_hashes.py`. Verify that the vault-init delta scenarios pass as tests, that the naming test passes, and that init/upgrade tests pass.

## 5. Verification

- [x] 5.1 Real-page check in a scratch vault: capture https://rossaprimavera.ru/article/c42539c8 (expect `published: 2026-04-09T06:25:00+03:00`, `modified: 2026-04-14T01:00:00+03:00`, `published_via: jsonld`), plus https://rossaprimavera.ru/article/7c7b02cb. Create synthetic source pages copying the dates and a concept page linked from both. Check that `wiki timeline` orders them 2026-04-09 before 2026-08-02, and that `wiki search --since 2026-05 --raw` returns only the August article. Record the results in design.md, then commit, push, and confirm CI passes.
