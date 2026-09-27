## ADDED Requirements

### Requirement: Record publication dates
Captures of URLs and saved web pages SHALL record `published` in raw frontmatter from the first of these that yields a parseable date:
1. the JSON-LD `datePublished` of the page's main article object;
2. a `<meta property="article:published_time">` (or `name=`) tag;
3. the first `<time datetime>` inside the article, or failing that on the page;
4. the heuristic date found by the metadata extractor.

`published` SHALL be an ISO 8601 timestamp including the source's UTC offset when the source gives a time, and a plain `YYYY-MM-DD` date when only a date is known. A time of day SHALL NOT be invented. The capture SHALL also record `published_via` (`jsonld`, `meta`, `time`, `heuristic`) and, when the page gives it (JSON-LD `dateModified` or `article:modified_time`), `modified` in the same format. Captures of `.md` files SHALL take `published` from an original frontmatter key `published` or `date` (`published_via: frontmatter`). Unparseable values SHALL be skipped in favour of the next source. With no date anywhere, `published`, `published_via` and `modified` SHALL be omitted.

#### Scenario: JSON-LD date with time zone
- **WHEN** a page's JSON-LD has `datePublished: 2026-04-09T06:25+03:00` and `dateModified: 2026-04-14T01:00+03:00`
- **THEN** the raw file records `published: 2026-04-09T06:25:00+03:00`, `modified: 2026-04-14T01:00:00+03:00` and `published_via: jsonld`

#### Scenario: Date-only source
- **WHEN** the only date signal is `<meta property="article:published_time" content="2026-04-09">`
- **THEN** `published` is `2026-04-09` with no time, and `published_via` is `meta`

#### Scenario: Structured data beats heuristics
- **WHEN** a page has a JSON-LD `datePublished` and also a different date in its text that the heuristic would pick
- **THEN** the JSON-LD date is recorded

#### Scenario: Web Clipper markdown
- **WHEN** a `.md` file with frontmatter `published: 2026-03-01` is captured
- **THEN** the raw file records `published: 2026-03-01` and `published_via: frontmatter`

#### Scenario: No date
- **WHEN** no date signal exists
- **THEN** the raw file has no `published`, `published_via` or `modified`

## MODIFIED Requirements

### Requirement: Re-derive source metadata
`wiki source-meta <raw file>` SHALL re-derive capture metadata for an existing raw file from its stored original (`original_file` under `raw/.orig/`) using the current extraction rules, and print at least `path`, `title`, `authors`, `published`, `modified`, `published_via`, `language` and `canonical_url`, along with the values recorded in the raw file. It SHALL NOT modify any file. For raw files without a stored original, it SHALL report the recorded values and `derivable: false`. `wiki source-meta --all` SHALL list every raw file whose known authors (recorded, else re-derived) are non-empty while its source page (if any) has no `authors`, or whose known `published` (recorded, else re-derived) is set while its source page (if any) has no `published`. Each item SHALL give the raw path, the source page path (or null if not ingested), `missing` (a list containing `authors` and/or `published`), and the known `authors` and `published` values.

#### Scenario: Backfill an older capture
- **WHEN** a raw file captured before authors were recorded has an `.orig` HTML with a JSON-LD author, and its source page has no `authors`
- **THEN** `wiki source-meta --all --json` lists that raw file with the source page path and the derived authors, and no file changes

#### Scenario: Read-only
- **WHEN** `wiki source-meta` runs on any raw file
- **THEN** every file in the vault is byte-identical afterwards

#### Scenario: No stored original
- **WHEN** the raw file came from a `.txt` capture
- **THEN** the output shows the recorded values and `derivable: false`

#### Scenario: Backfill a missing date
- **WHEN** a source page has `authors` but no `published`, and its raw file's `.orig` has JSON-LD `datePublished`
- **THEN** `wiki source-meta --all --json` lists it with `missing: ["published"]` and the derived `published` value
