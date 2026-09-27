# wiki-lint Specification

## Purpose

Gives a deterministic, structural health check of the vault — the mechanical half of the pattern's "lint" operation — so Claude can fix concrete problems and spend its judgement on semantic checks instead.

## Requirements


### Requirement: Structural checks
`wiki lint` SHALL check the vault and report each finding with a `severity` (`error`, `warning`, or `info`), a stable `code`, the affected `path`, and a `message`. It SHALL detect at least:
- `dead_link` (error): a wikilink that resolves to no page and no file in the vault
- `duplicate_title` (error): two pages whose names collide under the page-uniqueness rule
- `bad_filename` (error): a page filename that is not in NFC or would change under the title-to-filename rules
- `frontmatter_missing` / `frontmatter_invalid` (error): missing or unparseable frontmatter, or a required field absent
- `type_folder_mismatch` (error): frontmatter `type` does not match the page's folder
- `raw_missing` (error): a source page whose `raw` field names a nonexistent file
- `raw_modified` (error): a raw file whose body no longer matches its recorded `sha256`
- `orphan` (warning): a page with no inbound wikilinks from other pages (links from `index.md` do not count)
- `empty_summary` (warning): a page with an empty `summary`
- `index_stale` (warning): `index.md` differs from what `wiki index` would generate
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

### Requirement: Lint exit status and filtering
`wiki lint` SHALL exit 1 if any `error` finding exists, and 0 otherwise. `--strict` SHALL also make warnings produce exit 1. `--json` output SHALL include the findings list and counts per severity.

#### Scenario: Warnings only
- **WHEN** the only findings are orphans
- **THEN** `wiki lint` exits 0 and `wiki lint --strict` exits 1

### Requirement: Lint is read-only
`wiki lint` SHALL NOT modify any file.

#### Scenario: Lint does not fix
- **WHEN** lint finds a stale index
- **THEN** `index.md` is unchanged after lint runs
