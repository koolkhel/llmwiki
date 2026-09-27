## ADDED Requirements

### Requirement: Schema covers authorship
The `AGENTS.md` schema written by `wiki init` SHALL require that a source page records the source's authors, when known, as `authors: ["[[Name]]"]`, with each author linked to an entity page tagged `person` that lists their articles. It SHALL require claims to be attributed to their author, and name variants to be recorded as `aliases` on the person page. The ingest workflow SHALL include creating or updating the author pages from the raw file's `authors`, and asking the human when the raw file has none. The lint workflow SHALL include backfilling missing authors with `wiki source-meta --all`.

#### Scenario: Schema mentions authors
- **WHEN** `AGENTS.md` is inspected after init
- **THEN** it documents the `authors` field on source pages, person entity pages tagged `person`, attribution of claims, and `aliases` for name variants

#### Scenario: Workflows handle authors
- **WHEN** the rendered ingest and lint workflows are inspected
- **THEN** ingest includes the author-page step, and lint includes running `wiki source-meta --all` to backfill authors
