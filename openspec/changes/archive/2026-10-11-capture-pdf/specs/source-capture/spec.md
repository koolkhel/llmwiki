## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Duplicate detection
Before writing, `add-source` SHALL check existing raw files; a source whose `sha256` matches an existing raw file, or (for URLs) whose `normalized_url` matches, or (for PDFs) whose file bytes match an existing raw file's `original_sha256`, SHALL NOT be written again. The command SHALL succeed and report `duplicate_of` with the existing path.

#### Scenario: Same article via a tracking URL
- **WHEN** the user adds `https://example.org/post?utm_source=x` after previously adding `https://example.org/post`
- **THEN** no new raw file is created and the output reports `duplicate_of` pointing at the earlier file

#### Scenario: Same PDF again
- **WHEN** the user adds a PDF whose bytes are identical to a PDF captured earlier, even from a different path
- **THEN** no new raw file and no new copy under `raw/.orig/` is written, and the output reports `duplicate_of` with the earlier raw file

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
