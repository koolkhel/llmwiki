## ADDED Requirements

### Requirement: Schema covers chronology
The `AGENTS.md` schema written by `wiki init` SHALL contain a Chronology section requiring that:
- source pages record `published` (the date) copied from the raw file, when known;
- claims on concept and person pages state when and by whom they were made (e.g. "In April 2026, [[Author]] argued … ([[Source]])");
- concept and person pages keep a **Timeline** section of dated entries in chronological order, one per source;
- questions about change over time are answered using `wiki timeline`.

The ingest workflow SHALL include copying `published` and adding a Timeline entry. The query workflow SHALL direct time-related questions to `wiki timeline` and `--since`/`--until`/`--sort`. The lint workflow's backfill step SHALL fill in both authors and dates from `wiki source-meta --all`.

#### Scenario: Schema mentions chronology
- **WHEN** `AGENTS.md` is inspected after init
- **THEN** it documents `published` on source pages, dated claims, Timeline sections and `wiki timeline`

#### Scenario: Workflows handle dates
- **WHEN** the rendered ingest, query and lint workflows are inspected
- **THEN** ingest copies `published` and adds a Timeline entry, query mentions `wiki timeline`, and lint backfills `published`
