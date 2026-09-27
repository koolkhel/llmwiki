## MODIFIED Requirements

### Requirement: Structural checks
`wiki lint` SHALL check the vault and report each finding with a `severity` (`error`, `warning`, or `info`), a stable `code`, the affected `path`, and a `message`. It SHALL detect at least:
- `dead_link` (error): a wikilink that resolves to no page and no file in the vault
- `duplicate_title` (error): two pages whose names collide under the page-uniqueness rule
- `bad_filename` (error): a page filename that is not in NFC or would change under the title-to-filename rules
- `frontmatter_missing` / `frontmatter_invalid` (error): missing or unparseable frontmatter, a required field absent, or an optional field of the wrong type (e.g. `authors` that is not a list)
- `type_folder_mismatch` (error): frontmatter `type` does not match the page's folder
- `raw_missing` (error): a source page whose `raw` field names a nonexistent file
- `raw_modified` (error): a raw file whose body no longer matches its recorded `sha256`
- `orphan` (warning): a page with no inbound wikilinks from other pages (links from `index.md` do not count)
- `empty_summary` (warning): a page with an empty `summary`
- `index_stale` (warning): `index.md` differs from what `wiki index` would generate
- `missing_authors` (warning): a source page whose raw file records `authors` but whose own `authors` is missing or empty
- `pending_source` (info): a raw source that is not yet ingested

#### Scenario: Dead link
- **WHEN** a page links `[[Nonexistent]]` and no such page exists
- **THEN** lint reports a `dead_link` error naming the page and the link target

#### Scenario: Tampered raw file
- **WHEN** someone edits the body of a file under `raw/`
- **THEN** lint reports `raw_modified` for that file

#### Scenario: Clean vault
- **WHEN** a freshly initialised vault is linted
- **THEN** lint reports no errors or warnings and exits 0

#### Scenario: Source page lost the author
- **WHEN** a raw file records `authors: [Владимир Колдин]` and its source page has no `authors`
- **THEN** lint reports a `missing_authors` warning for the source page naming the raw authors

#### Scenario: Authors recorded
- **WHEN** the source page has `authors: ["[[Владимир Колдин]]"]`
- **THEN** no `missing_authors` warning is reported for it

#### Scenario: authors of the wrong type
- **WHEN** a page has `authors: Владимир Колдин` (a string, not a list)
- **THEN** lint reports `frontmatter_invalid` for that page
