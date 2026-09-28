# wiki-lint Specification

## Purpose

Gives a deterministic, structural health check of the vault — the mechanical half of the pattern's "lint" operation — so Claude can fix concrete problems and spend its judgement on semantic checks instead.

## Requirements


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
- `missing_published` (warning): a source page whose raw file records `published` but whose own `published` is missing or empty
- `pending_source` (info): a raw source that is not yet ingested
- `template_merge_pending` (info): a `<path>.new` written by `wiki upgrade` next to a template-managed file, not yet merged and removed

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

#### Scenario: Pending template merge
- **WHEN** `wiki upgrade` left `AGENTS.md.new` in the vault
- **THEN** lint reports `template_merge_pending` (info) for `AGENTS.md.new` and still exits 0

#### Scenario: Source page lost the date
- **WHEN** a raw file records `published: 2026-04-09T06:25:00+03:00` and its source page has no `published`
- **THEN** lint reports a `missing_published` warning for the source page naming the raw date

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

### Requirement: Digest coverage checks
For every raw file with `format: rp-digest` that is ingested (at least one source page has `raw:` pointing at it), `wiki lint` SHALL parse its items as `wiki source-items-rp` does and report:
- `rp_item_missing` (warning): an item number for which no source page with that `raw` and `item` exists;
- `rp_item_mismatch` (warning): an item page whose `published` differs from the item's date, whose `commentary` is true without a comment (or missing or false with one), or whose `item` is not an item of the digest.

`missing_authors` SHALL NOT be reported for source pages that have an `item`: the raw file's authors belong to the issue, and the hub page carries them. A raw file that cannot be parsed SHALL be reported once as `rp_item_mismatch` with the parse error and not otherwise checked. Pending raw files SHALL NOT be checked. `item`, `outlet`, `via` and `commentary` of the wrong type SHALL be reported as `frontmatter_invalid`.

#### Scenario: Item not ingested
- **WHEN** a digest has 3 items and source pages exist for items 1 and 3
- **THEN** lint warns `rp_item_missing` for item 2

#### Scenario: Comment flag wrong
- **WHEN** item 2 has an editorial comment but its page has no `commentary`
- **THEN** lint warns `rp_item_mismatch` for that page

#### Scenario: Wrong field type
- **WHEN** a source page has `commentary: "yes"`
- **THEN** lint reports `frontmatter_invalid` for it

#### Scenario: Item pages without authors
- **WHEN** the digest's raw file records `authors: [Новости недели]` and an item page has no `authors`
- **THEN** no `missing_authors` warning is reported for the item page

#### Scenario: Complete digest
- **WHEN** every item has a matching page with correct `published` and `commentary`
- **THEN** lint reports no `rp_item_*` findings
