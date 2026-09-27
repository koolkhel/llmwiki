## Purpose

Provides the navigation layer of the pattern — a generated catalog (`index.md`), an append-only activity record (`log.md`), page search, and a vault status summary — so Claude can orient itself in the wiki without reading every page.

## ADDED Requirements

### Requirement: Generated index
`wiki index` SHALL regenerate `index.md` listing every page under `wiki/`, grouped by type in the fixed order sources, entities, concepts, analyses, each entry being a wikilink followed by the page's `summary`. Within a group, entries SHALL be sorted case-insensitively by title. The file SHALL begin with a notice that it is generated. Output SHALL be deterministic for a given set of pages.

#### Scenario: Index reflects new page
- **WHEN** a new concept page with summary "Short description" is created and `wiki index` is run
- **THEN** `index.md` contains `- [[<title>]] — Short description` under the Concepts heading

#### Scenario: Page without summary
- **WHEN** a page has an empty summary
- **THEN** its index entry is the wikilink alone

### Requirement: Append-only log
`wiki log <operation> <message>` SHALL append one entry to `log.md` of the form `## [YYYY-MM-DD HH:MM] <operation> | <message>` (local time), where `<operation>` is one of `ingest`, `query`, `lint`, `init`, `note`. It SHALL never rewrite or remove existing content. `--detail <text>` MAY add a body paragraph under the heading.

#### Scenario: Greppable entries
- **WHEN** Claude runs `wiki log ingest "Some Article"` three times across a day
- **THEN** `grep "^## \[" log.md` returns the three entries in chronological order and earlier content is unchanged

#### Scenario: Unknown operation
- **WHEN** `wiki log deploy "x"` is run
- **THEN** it fails with a usage error and `log.md` is unchanged

### Requirement: Search pages
`wiki search <query>` SHALL return pages matching all query terms (case-insensitive, accent-insensitive), searching title, summary, tags and body, ranked so title matches outrank summary/tag matches, which outrank body-only matches. Each result SHALL include `path`, `title`, `type`, `summary`, `link`, and a short body snippet around the first match. `--type` SHALL restrict results to one page type, `--limit` SHALL cap the count (default 20), and `--raw` SHALL search raw sources instead of wiki pages.

#### Scenario: Title outranks body
- **WHEN** page A has the term in its title and page B only in its body
- **THEN** A is listed before B

#### Scenario: Accent-insensitive
- **WHEN** the query is `cafe` and a page title is `Café culture`
- **THEN** that page is returned

### Requirement: Vault status
`wiki status` SHALL report the vault path, page counts per type, total and pending raw source counts, the list of pending raw sources, whether `index.md` is stale, and the most recent log entry heading.

#### Scenario: Status after capture
- **WHEN** one URL has been captured but no source page references it
- **THEN** `wiki status --json` reports one pending source with its path and title
