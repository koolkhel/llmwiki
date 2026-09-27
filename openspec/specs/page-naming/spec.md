# page-naming Specification

## Purpose

Makes a page's title its filename, so Obsidian `[[wikilinks]]` read naturally, while the CLI — not the LLM — owns every rule needed to make that safe across filesystems, Unicode forms and duplicate titles.

## Requirements


### Requirement: Title to filename
Converting a page title to a filename SHALL: normalise to Unicode NFC; replace each character that is illegal in filenames on macOS, Linux or Windows (`/ \ : * ? " < > |` and control characters) or that breaks Obsidian wikilinks (`# ^ [ ] |`) with a single space; collapse runs of whitespace to one space; strip leading and trailing whitespace and dots; truncate so the filename including `.md` is at most 200 bytes in UTF-8 without splitting a character; and append `.md`. A title that is empty after this process SHALL be rejected. Emoji and other non-ASCII characters SHALL be preserved.

#### Scenario: Illegal characters
- **WHEN** the title is `A/B: "Test"?`
- **THEN** the filename is `A B Test.md`

#### Scenario: NFD input
- **WHEN** the title is supplied in NFD form (e.g. `e` followed by a combining acute accent)
- **THEN** the filename uses the NFC precomposed character

#### Scenario: Long multibyte title
- **WHEN** the title is 300 Cyrillic characters
- **THEN** the filename is at most 200 UTF-8 bytes, ends in `.md`, and contains no partial character

#### Scenario: Title with nothing usable
- **WHEN** the title is `???`
- **THEN** the operation fails with a usage error

### Requirement: Page uniqueness
Page names SHALL be unique across all of `wiki/` when compared case-insensitively after NFC normalisation, regardless of folder, because Obsidian resolves wikilinks by basename.

#### Scenario: Same title in another folder
- **WHEN** `wiki/concepts/Transformers.md` exists and a new entity page titled `transformers` is requested
- **THEN** creation fails with error code `duplicate_title`, naming the existing page

### Requirement: Create a page
`wiki new-page --type <source|entity|concept|analysis> "<title>"` SHALL create the page in the folder for that type with frontmatter `type`, `summary` (empty), `sources` (empty list), `created` and `updated` (ISO dates), and `tags` (empty list), and for type `source` a required `--raw <path>` stored as `raw`. It SHALL output the created path and the exact wikilink text to use for the page. It SHALL NOT overwrite an existing page.

#### Scenario: Create a concept page
- **WHEN** Claude runs `wiki new-page --type concept "Retrieval-Augmented Generation" --json`
- **THEN** `wiki/concepts/Retrieval-Augmented Generation.md` exists with the required frontmatter and the output includes `"link": "[[Retrieval-Augmented Generation]]"`

#### Scenario: Source page must reference raw
- **WHEN** `wiki new-page --type source "X"` is run without `--raw`, or `--raw` names a file not under `raw/`
- **THEN** the command fails with a usage error and creates nothing

### Requirement: Wikilink resolution
The CLI SHALL resolve wikilinks the way Obsidian does for this vault: `[[Name]]`, `[[Name|alias]]`, `[[Name#Heading]]` and `[[Name#^block]]` resolve to the page whose basename matches `Name` case-insensitively after NFC normalisation; `[[folder/Name]]` resolves by vault-relative path. Links inside fenced code blocks and inline code SHALL be ignored.

#### Scenario: Alias and heading
- **WHEN** a page contains `[[retrieval-augmented generation#History|RAG]]`
- **THEN** it resolves to `wiki/concepts/Retrieval-Augmented Generation.md`

#### Scenario: Link inside code
- **WHEN** a page contains `` `[[Not A Page]]` ``
- **THEN** it is not treated as a link
