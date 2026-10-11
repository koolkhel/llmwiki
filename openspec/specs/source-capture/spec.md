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
Before writing, `add-source` SHALL check existing raw files; a source whose `sha256` matches an existing raw file, or (for URLs) whose `normalized_url` matches, or (for PDFs) whose file bytes match an existing raw file's `original_sha256`, SHALL NOT be written again. The command SHALL succeed and report `duplicate_of` with the existing path.

#### Scenario: Same article via a tracking URL
- **WHEN** the user adds `https://example.org/post?utm_source=x` after previously adding `https://example.org/post`
- **THEN** no new raw file is created and the output reports `duplicate_of` pointing at the earlier file

#### Scenario: Same PDF again
- **WHEN** the user adds a PDF whose bytes are identical to a PDF captured earlier, even from a different path
- **THEN** no new raw file and no new copy under `raw/.orig/` is written, and the output reports `duplicate_of` with the earlier raw file

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
`wiki source-meta <raw file>` SHALL re-derive capture metadata for an existing raw file from its stored original (`original_file` under `raw/.orig/`) using the current extraction rules, and print at least `path`, `title`, `authors`, `published`, `modified`, `published_via`, `language` and `canonical_url`, along with the values recorded in the raw file. A stored PDF original SHALL be re-derived with the PDF extraction rules (yielding `title`, `authors` and `doi`; `published`, `modified`, `published_via`, `language` and `canonical_url` are null), and never parsed as HTML. It SHALL NOT modify any file. For raw files without a stored original, or whose stored original is not present on this machine, it SHALL report the recorded values and `derivable: false`. `wiki source-meta --all` SHALL list every raw file whose known authors (recorded, else re-derived) are non-empty while its source page (if any) has no `authors`, or whose known `published` (recorded, else re-derived) is set while its source page (if any) has no `published`. Each item SHALL give the raw path, the source page path (or null if not ingested), `missing` (a list containing `authors` and/or `published`), and the known `authors` and `published` values.

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

#### Scenario: PDF capture
- **WHEN** `wiki source-meta` runs on a PDF capture whose PDF is in `raw/.orig/`
- **THEN** the derived values come from the PDF (title from page 1), and no HTML extraction is attempted

#### Scenario: PDF not on this machine
- **WHEN** the vault was cloned and `raw/.orig/` lacks the git-ignored PDF
- **THEN** the output shows the recorded values and `derivable: false`

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

### Requirement: Mark digest captures
When `wiki add-source` captures a page from rossaprimavera.ru, whether by URL or from a saved `.html` whose original URL is on that site, and the captured HTML contains digest dateline paragraphs, the raw file's frontmatter SHALL include `format: rp-digest`. PDF captures SHALL receive `format: pdf`. No other capture SHALL receive a `format` field. The body extraction SHALL be unchanged, and existing raw files SHALL NOT be rewritten.

#### Scenario: Digest URL
- **WHEN** the user captures a rossaprimavera.ru digest page with datelines
- **THEN** the raw file's frontmatter has `format: rp-digest`

#### Scenario: Ordinary article on the same site
- **WHEN** the user captures a rossaprimavera.ru article without datelines
- **THEN** the raw file has no `format` field

#### Scenario: Other site with the same markup
- **WHEN** a page on another domain happens to use `class="block_date"` paragraphs
- **THEN** the raw file has no `format` field

### Requirement: Capture a PDF file
`wiki add-source <path>` for a `.pdf` file SHALL extract the document's text as markdown and write it to a new file under `raw/`. Only single-column documents with a text layer are supported.

The body SHALL be built from the page layout:
- the title as a `# ` heading;
- section headings (text set apart from body text by a bold face or a larger size) as `## ` headings;
- body paragraphs, with a paragraph that continues across a page break joined into one, and words hyphenated at a line end rejoined; consecutive short lines aligned with each other (verse, epigraphs) stay one block that keeps its line breaks;
- figure and table captions (smaller text starting with `Figure`/`Fig.`/`Table` and a number) as `> ` blockquote lines;
- footnote markers (raised, smaller digits following body text) as `[^n]`, and footnote text (small text at the foot of a page starting with its number) as `[^n]: …` definitions at the end of the body;
- the references section under a `## References` heading (or the document's own heading for it), with each entry as one line, whether entries are numbered or author–year (entries told apart by their hanging indent);
- a table of contents (entries after a `Contents` heading that end with a page number) as one `- ` list, without dot leaders.

Rotated text (such as a preprint server's vertical margin stamp) SHALL be ignored. A body paragraph that would start with markdown block syntax (`>`, `#`, `|`) SHALL be escaped with a backslash.

Page numbers and running headers and footers (text repeated at the same position on most pages) SHALL be dropped. Whitespace SHALL be normalised, so that tabs and runs of spaces between words become one space.

The frontmatter SHALL contain:
- `kind: file` and `format: pdf`;
- `title`: the largest text on the upper half of page 1 when it is larger than the body text, else the first bold line(s) at the top of page 1 that are not a section heading, else the PDF metadata title unless it is a placeholder (such as `Untitled` or `Microsoft Word - …`), else the filename stem;
- `original_path` (absolute) and `original_file`, the PDF's bytes copied unmodified under `raw/.orig/`;
- `original_sha256` and `original_size` of the PDF bytes;
- `pages`, the page count;
- `captured_at`, `sha256` of the body, and `extractor`, which names the extraction library and its version;
- `doi`, when page 1 contains a DOI;
- `authors`, only as described below.

Authors SHALL be taken from the PDF metadata author field when it holds person-like names (at least two words made of letters per name). Otherwise they SHALL come from the line(s) between the title and the abstract or first heading on page 1, when every comma- or "and"-separated part is a person-like name after superscript markers and affiliation digits are removed. Otherwise `authors` SHALL be omitted. `published` SHALL NOT be recorded from the PDF's creation or modification dates.

The command SHALL exit with code 2, write nothing to `raw/` or `raw/.orig/`, and report one of these error codes:
- `no_text_layer` when the document has no extractable text (e.g. a scan);
- `multi_column` when the body text is laid out in two or more columns;
- `pdf_encrypted` when the document cannot be opened without a password;
- `pdf_unreadable` when the file is not a readable PDF.

The source PDF SHALL NOT be modified or moved, and capturing a PDF SHALL NOT access the network. `--url` SHALL be rejected for PDF sources as for other non-HTML files.

#### Scenario: Single-column paper
- **WHEN** the user runs `wiki add-source ~/Downloads/paper.pdf --json` for a single-column paper with a text layer
- **THEN**:
  - a raw file is created with `kind: file`, `format: pdf`, the title from page 1, `pages`, `original_sha256`, `original_size` and `extractor`;
  - the PDF is copied byte-identical to `raw/.orig/`;
  - the JSON output contains the new `path` and `status: "pending"`

#### Scenario: Wrong metadata title
- **WHEN** the PDF's metadata title is "Paper v33" and page 1 shows the paper's title in the largest type
- **THEN** `title` is the title shown on page 1

#### Scenario: Structure preserved
- **WHEN** the paper has bold numbered section headings, a caption "Figure 2: …", a footnote 3 and a numbered reference list
- **THEN**:
  - the body contains `## ` lines for the sections and a `> Figure 2: …` line;
  - the footnote marker appears as `[^3]` in its sentence, and `[^3]: …` appears at the end of the body;
  - each reference is one line starting with its number

#### Scenario: Author–year references and a margin stamp
- **WHEN** a preprint has a vertical margin stamp on page 1 and an unnumbered reference list whose entries have a hanging indent
- **THEN** the stamp's text is not in the body, and each reference entry is one line

#### Scenario: Paragraph across a page break
- **WHEN** a paragraph starts at the bottom of page 4 and continues on page 5, with the page number "4" printed between them
- **THEN** the body contains the paragraph as one paragraph and does not contain the page number

#### Scenario: Scanned PDF
- **WHEN** the PDF consists only of page images
- **THEN** the command exits 2 with `no_text_layer` and writes nothing

#### Scenario: Two-column paper
- **WHEN** the body text of the PDF is laid out in two columns
- **THEN** the command exits 2 with `multi_column` and writes nothing

#### Scenario: Password-protected PDF
- **WHEN** the PDF requires a password to open
- **THEN** the command exits 2 with `pdf_encrypted` and writes nothing

#### Scenario: Not a PDF
- **WHEN** a file named `x.pdf` contains plain text or a truncated PDF
- **THEN** the command exits 2 with `pdf_unreadable` and writes nothing

#### Scenario: Creation date is not a publication date
- **WHEN** the PDF metadata has a creation date and the text states no publication date
- **THEN** the raw file has no `published`

#### Scenario: Authors from page 1
- **WHEN** the PDF metadata has no author and page 1 shows "Anna Example¹, Boris Sample²" between the title and "Abstract"
- **THEN** `authors` is `[Anna Example, Boris Sample]`

#### Scenario: No recognisable authors
- **WHEN** the metadata author is a username such as `jdoe` and page 1 has no name line before the abstract
- **THEN** the raw file has no `authors`

#### Scenario: DOI on page 1
- **WHEN** page 1 contains `https://doi.org/10.1234/abcd.5678`
- **THEN** the raw file records `doi: 10.1234/abcd.5678`
