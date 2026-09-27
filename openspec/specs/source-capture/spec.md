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
