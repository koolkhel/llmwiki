# source-capture Specification

## Purpose

Brings raw material into the vault as immutable, provenance-tagged markdown files — from URLs or local text files — so that every wiki claim can be traced back to a faithful copy of its source.

## Requirements


### Requirement: Capture a URL
`wiki add-source <url>` SHALL fetch the page, extract its main text, and write a markdown file under `raw/` whose frontmatter contains at least: `kind: url`, `original_url`, `canonical_url` (when known), `normalized_url`, `title`, `captured_at` (ISO 8601 UTC), `sha256` of the extracted text, and when available `published`, `language`, and `extractor`. The body SHALL be the extracted main text as markdown, preserving headings, paragraph breaks, lists and links where the page provides them. The fetched HTML SHALL be saved unmodified under `raw/.orig/` and referenced from the frontmatter as `original_file`.

#### Scenario: Successful capture
- **WHEN** the user runs `wiki add-source https://example.org/post --json` and the page is reachable
- **THEN** a new file `raw/<date>-<title>.md` exists with the required frontmatter and extracted body, the HTML is stored under `raw/.orig/`, and the JSON output contains the new file's `path`, `sha256` and `status: "pending"`

#### Scenario: Fetch or extraction failure
- **WHEN** the URL returns an HTTP error, times out, or yields no extractable text
- **THEN** the command exits with code 2, reports an error code identifying the failure kind, and writes nothing to `raw/`

### Requirement: Capture a local text file
`wiki add-source <path>` for a UTF-8 `.txt` or `.md` file SHALL copy its content into a new file under `raw/` with frontmatter containing `kind: file`, `original_path` (absolute), `title` (from an existing frontmatter title, else the first markdown heading, else the filename stem), `captured_at`, and `sha256` of the content. Pre-existing frontmatter in a `.md` source SHALL be preserved under an `original_frontmatter` key. The source file itself SHALL NOT be modified or moved.

#### Scenario: Plain text file
- **WHEN** the user runs `wiki add-source ~/Downloads/transcript.txt`
- **THEN** a new raw file is created with `kind: file`, the transcript text as body, and the original file is untouched

#### Scenario: Unsupported or undecodable file
- **WHEN** the path is a binary file, a directory, or not valid UTF-8
- **THEN** the command exits with code 2 and writes nothing to `raw/`

### Requirement: Duplicate detection
Before writing, `add-source` SHALL check existing raw files; a source whose `sha256` matches an existing raw file, or (for URLs) whose `normalized_url` matches, SHALL NOT be written again. The command SHALL succeed and report `duplicate_of` with the existing path.

#### Scenario: Same article via a tracking URL
- **WHEN** the user adds `https://example.org/post?utm_source=x` after previously adding `https://example.org/post`
- **THEN** no new raw file is created and the output reports `duplicate_of` pointing at the earlier file

### Requirement: Raw file naming
Raw files SHALL be named `YYYY-MM-DD-<title>.md` using the capture date and the title processed with the page-naming sanitisation rules. If that name already exists, a short suffix derived from the content hash SHALL be appended.

#### Scenario: Two different sources with the same title on the same day
- **WHEN** two different sources titled "Weekly Notes" are captured on the same day
- **THEN** both are stored under distinct filenames and neither overwrites the other

### Requirement: Raw files are immutable
No `wiki` command SHALL modify or delete a file under `raw/` after it has been written.

#### Scenario: Status changes do not touch raw files
- **WHEN** a raw source becomes ingested
- **THEN** the raw file's bytes are unchanged

### Requirement: Ingestion status is derived
A raw source SHALL be considered `ingested` when at least one page in `wiki/sources/` declares it in its `raw` frontmatter field, and `pending` otherwise. `wiki status` SHALL list pending sources.

#### Scenario: Source summary page marks ingestion
- **WHEN** `wiki/sources/Some Article.md` has frontmatter `raw: raw/2026-09-27-Some Article.md`
- **THEN** `wiki status --json` reports that raw file as ingested and it no longer appears in the pending list

### Requirement: Capture a saved web page
`wiki add-source <path>` for a `.html` or `.htm` file SHALL extract the page's main text as markdown with the same extraction used for URL capture, and write it to a new file under `raw/`. The original URL SHALL be taken from `--url <url>` if given, else from the page's `<link rel="canonical">`, else from its `og:url` meta tag, else from a `<!-- saved from url=… -->` comment. Relative values are resolved against the others where possible, and only `http(s)` URLs are accepted.

When a URL is known, the frontmatter SHALL be that of a URL capture (`kind: url`, `original_url`, `canonical_url` when known, `normalized_url`, `title`, `captured_at`, `sha256`, `extractor`, `original_file`, and `published`/`language` when available), plus `captured_via: saved-file` and `original_path` (absolute). When no URL is known, the frontmatter SHALL use `kind: file` with `title`, `original_path`, `captured_at`, `sha256`, `extractor` and `original_file`, and the command SHALL succeed with a warning that suggests `--url`.

The saved file's bytes SHALL be copied unmodified to `raw/.orig/` and referenced as `original_file`. Companion asset folders (such as `<name>_files/`) SHALL be ignored. The saved file SHALL NOT be modified or moved. Capturing a saved page SHALL NOT access the network. Duplicate detection SHALL apply as for other sources, so a saved page and a direct capture of the same URL are duplicates of each other. `--url` SHALL be rejected as a usage error for sources that are not `.html`/`.htm` files.

#### Scenario: Saved page with canonical URL
- **WHEN** the user runs `wiki add-source "~/Downloads/Article.html"` and the page has `<link rel="canonical" href="https://example.org/post">`
- **THEN** a raw file is created with `kind: url`, `captured_via: saved-file`, `original_url: https://example.org/post`, the extracted article as markdown, and an unmodified copy of the HTML under `raw/.orig/`

#### Scenario: URL from og:url or the saved-from comment
- **WHEN** a saved page has no canonical link but has an `og:url` meta tag, or only a `<!-- saved from url=(0027)https://example.org/post -->` comment
- **THEN** that URL is recorded as `original_url`

#### Scenario: Explicit URL wins
- **WHEN** the user passes `--url https://example.org/real` for a page whose canonical link says something else
- **THEN** `original_url` is `https://example.org/real`

#### Scenario: No URL known
- **WHEN** a saved page contains none of the URL signals and no `--url` is given
- **THEN** the page is captured with `kind: file`, the command exits 0, and the output includes a warning suggesting `--url`

#### Scenario: Duplicate of a direct URL capture
- **WHEN** `https://example.org/post` was captured by URL earlier, and a saved copy of the same article (canonical `https://example.org/post?utm_source=x`) is added
- **THEN** no new raw file is written and the output reports `duplicate_of` with the earlier file

#### Scenario: Offline
- **WHEN** a saved page is captured while network access is unavailable
- **THEN** the capture succeeds and no network connection is attempted

#### Scenario: Nothing extractable
- **WHEN** the saved page has no extractable main text
- **THEN** the command exits with code 2 (`extraction_failed`) and writes nothing to `raw/`

#### Scenario: --url on a non-HTML source
- **WHEN** the user runs `wiki add-source notes.txt --url https://example.org`
- **THEN** the command exits with code 2 and writes nothing

### Requirement: Record authors
Captures of URLs, saved web pages and `.md` files SHALL record the source's authors in raw frontmatter as `authors`: an ordered list of names, each whitespace-normalised, with duplicates removed and the first occurrence kept. Authors SHALL be taken from the first of these that yields at least one name:
1. JSON-LD on the page: the `author` of the page's main article object (a Person/Organization `name`, a list of them, or a plain string);
2. the page author found by the text extractor's metadata;
3. the authors found by the news-metadata extractor;
4. for `.md` files only, an `author` or `authors` key in the file's original frontmatter.

Authors from elements that describe other content on the page (related-article widgets, sidebars) SHALL NOT be recorded. When no authors are found, the `authors` key SHALL be omitted rather than written empty. `.txt` captures record no authors.

#### Scenario: Author in JSON-LD and byline
- **WHEN** a page has `"author":[{"@type":"Person","name":"Владимир Колдин"}]` in JSON-LD and a sidebar widget listing "Максим Карев, Владимир Колдин" for another article
- **THEN** the raw file records `authors: [Владимир Колдин]`, without Максим Карев

#### Scenario: Several authors keep their order
- **WHEN** the article's JSON-LD lists authors "Anna A" then "Boris B"
- **THEN** `authors` is `[Anna A, Boris B]`

#### Scenario: Metadata fallback
- **WHEN** a page has no JSON-LD author but has `<meta name="author" content="Jane Doe">`
- **THEN** `authors` is `[Jane Doe]`

#### Scenario: Web Clipper markdown
- **WHEN** a `.md` file with frontmatter `author: "[[Jane Doe]]"` or `author: [Jane Doe, John Roe]` is captured
- **THEN** `authors` holds the plain names (`[Jane Doe]` or `[Jane Doe, John Roe]`), without wikilink brackets

#### Scenario: No author anywhere
- **WHEN** no author signal exists
- **THEN** the raw file has no `authors` key

### Requirement: Re-derive source metadata
`wiki source-meta <raw file>` SHALL re-derive capture metadata for an existing raw file from its stored original (`original_file` under `raw/.orig/`) using the current extraction rules, and print at least `path`, `title`, `authors`, `published`, `language` and `canonical_url`, along with the values recorded in the raw file. It SHALL NOT modify any file. For raw files without a stored original, it SHALL report the recorded values and `derivable: false`. `wiki source-meta --all` SHALL list every raw file whose re-derived or recorded authors are non-empty while its source page (if any) has no `authors`, giving the raw path, the source page path (or null if not ingested) and the authors.

#### Scenario: Backfill an older capture
- **WHEN** a raw file captured before authors were recorded has an `.orig` HTML with a JSON-LD author, and its source page has no `authors`
- **THEN** `wiki source-meta --all --json` lists that raw file with the source page path and the derived authors, and no file changes

#### Scenario: Read-only
- **WHEN** `wiki source-meta` runs on any raw file
- **THEN** every file in the vault is byte-identical afterwards

#### Scenario: No stored original
- **WHEN** the raw file came from a `.txt` capture
- **THEN** the output shows the recorded values and `derivable: false`
