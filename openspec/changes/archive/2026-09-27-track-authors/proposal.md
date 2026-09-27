## Why

Ingesting https://rossaprimavera.ru/article/7c7b02cb produced "no author stated", although the article is by Владимир Колдин. A spike showed the author appears in the byline (`<a class="author">`) and in JSON-LD (`"author":[{"@type":"Person",…}]`). Both extractors already in the stack found it (trafilatura metadata `author`, and mcmetadata's `other.authors`), but capture never stores an author, and trafilatura removes the byline from the body. So the name reaches neither the raw file nor the agent. For this user, authorship is essential: who wrote a claim matters as much as the claim.

## What Changes

- **Capture records authors.** URL, saved-page and `.md` captures write an ordered `authors` list to raw frontmatter. The sources, in priority order: JSON-LD `author`, trafilatura's author, mcmetadata's authors, and, for `.md`, an `author`/`authors` key in the original frontmatter (e.g. from Obsidian Web Clipper). The field is omitted when nothing is found.
- **Authors become people in the wiki.** The schema and the ingest workflow require source pages to carry `authors: ["[[Name]]"]`, with each author an entity page tagged `person`. The workflow creates or updates that page, adds the article to it, and attributes claims to their author. Name variants go in Obsidian `aliases:`.
- **Backfill for existing captures:** a new `wiki source-meta <raw file>` re-derives metadata (including authors) from the stored `raw/.orig/` HTML without modifying anything. `wiki source-meta --all` lists raw files whose derived authors are missing from their source page. The lint workflow uses it to fill in older source pages.
- **Lint:** a new `missing_authors` warning when a raw file records authors but its source page's `authors` is missing or empty. `authors`, when present, must be a list (`frontmatter_invalid` otherwise).
- **Search:** `wiki search --author <name>` restricts results to sources (or raw files, with `--raw`) whose authors match every word of the name, using the existing word-form matching, so `Колдина` finds `Колдин`. The query terms become optional when `--author` is given.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `source-capture`: new requirements "Record authors" and "Re-derive source metadata".
- `wiki-lint`: "Structural checks" gains `missing_authors`.
- `wiki-navigation`: "Search pages" gains `--author`, and query terms become optional when it is given.
- `vault-init`: new requirement "Schema covers authorship" (schema and workflow wording).

## Impact

- Code: `fetch.py` (author extraction, including JSON-LD parsing), `sources.py` (the `authors` field, `source-meta`), `lint.py`, `search.py`, `pages.py` (`authors` validation), `cli.py` (the `source-meta` command and `--author`), templates (`AGENTS.md`, ingest and lint workflows), README, tests.
- No new dependencies.
- Existing vaults: raw files are never rewritten. Old captures get authors on their source pages through `source-meta` backfill. Existing vaults get the new workflow wording only after deleting those files and re-running `wiki init`, as documented.
