## ADDED Requirements

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
