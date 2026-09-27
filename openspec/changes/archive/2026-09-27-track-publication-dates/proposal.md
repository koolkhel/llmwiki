## Why

The user needs to compare what was said when. URL captures already store `published`, but:
- it comes from htmldate's heuristic rather than the page's own structured data;
- it loses the time and timezone (`2026-04-09T00:00:00` for an article whose JSON-LD says `2026-04-09T06:25+03:00`);
- it ignores later edits (the same article has `dateModified` five days later);
- it can simply be wrong (an earlier Wikipedia capture got the page's 2002 creation date).

The date also never reaches the wiki: source pages have no `published`, the schema doesn't ask for dated claims, and nothing sorts or filters by time.

## What Changes

- **Capture records dates properly:**
  - `published` is taken from JSON-LD `datePublished`, then `article:published_time`, then `<time datetime>`, then the heuristic;
  - it is stored as an ISO 8601 timestamp with its timezone, or as a plain date when only a date is known (no invented midnight);
  - `modified` (`dateModified` or `article:modified_time`) and `published_via` (`jsonld`/`meta`/`time`/`heuristic`/`frontmatter`) are recorded too;
  - saved `.html` pages work the same way, and `.md` clips take `published`/`date` from their own frontmatter.
- **Backfill:** `wiki source-meta` re-derives the dates too, and `--all` lists sources whose page lacks authors **or** `published`, saying which.
- **The wiki carries dates:**
  - source pages copy `published` (the date) from the raw file, with a new `missing_published` lint warning;
  - the schema's new Chronology section requires dated claims on concept and person pages, plus a Timeline section in date order;
  - the ingest, query and lint workflows are updated to match.
- **Querying by time:**
  - `wiki search --since/--until` (`YYYY`, `YYYY-MM` or `YYYY-MM-DD`, inclusive) and `--sort oldest|newest`;
  - a new **`wiki timeline <page>`** lists every source connected to a concept or person page (or `--author X`) in publication order, with date, authors and summary, with undated sources last.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `source-capture`: a new requirement "Record publication dates"; "Re-derive source metadata" gains dates and a `missing` list.
- `wiki-lint`: "Structural checks" gains `missing_published`.
- `wiki-navigation`: "Search pages" gains `--since`, `--until` and `--sort`; a new requirement "Timeline".
- `vault-init`: a new requirement "Schema covers chronology".

## Impact

- Code: `fetch.py` (date extraction), `sources.py` (frontmatter, `source-meta`), `lint.py`, `search.py` (filters and sorting), a new `timeline.py`, `cli.py` (the `timeline` command and search options), templates (`AGENTS.md` Chronology section; ingest, query and lint workflows), `known_hashes.json`, README, tests.
- **`source-meta --all` JSON changes:** items gain `missing` and `published`. The spec changes accordingly, and the lint workflow template consumes the new shape.
- Existing raw files keep their recorded `published`. Better dates reach source pages through the backfill.
- No new dependencies.
