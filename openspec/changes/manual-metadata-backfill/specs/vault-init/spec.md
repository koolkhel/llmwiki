## MODIFIED Requirements

### Requirement: Schema covers authorship
The `AGENTS.md` schema written by `wiki init` SHALL require that a source page records the source's authors, when known, as `authors: ["[[Name]]"]`, with each author linked to an entity page tagged `person` that lists their articles. It SHALL require claims to be attributed to their author, and name variants to be recorded as `aliases` on the person page. Source-page `authors` SHALL come only from the raw file's `authors` or from the human: the schema SHALL forbid the agent to infer authors from the text, to look them up, or to change authors that are already set. The ingest workflow SHALL include creating or updating the author pages from the raw file's `authors`, and, when the raw file has none, SHALL leave `authors` empty and tell the human. The lint workflow SHALL include running `wiki source-meta --all` and presenting missing authors to the human as a checklist, without editing any page.

#### Scenario: Schema mentions authors
- **WHEN** `AGENTS.md` is inspected after init
- **THEN** it documents the `authors` field on source pages, person entity pages tagged `person`, attribution of claims, and `aliases` for name variants

#### Scenario: Workflows handle authors
- **WHEN** the rendered ingest and lint workflows are inspected
- **THEN** ingest includes the author-page step, and lint includes running `wiki source-meta --all` to report missing authors

#### Scenario: No guessing authors
- **WHEN** the rendered ingest workflow and `AGENTS.md` are inspected
- **THEN** they say that when the raw file records no authors, `authors` stays empty and the human is told, and neither tells the agent to look for a byline in the text

#### Scenario: Lint backfill is report-only
- **WHEN** the rendered lint workflow is inspected
- **THEN** its backfill step says to report `wiki source-meta --all` items to the human and not to edit source pages

### Requirement: Schema covers chronology
The `AGENTS.md` schema written by `wiki init` SHALL contain a Chronology section requiring that:
- source pages record `published` (the date) copied from the raw file, when known, and otherwise only a value the human enters; the agent never infers a date from the text, never looks one up, and never changes an existing `published`;
- claims on concept and person pages state when and by whom they were made (e.g. "In April 2026, [[Author]] argued … ([[Source]])");
- concept and person pages keep a **Timeline** section of dated entries in chronological order, one per source, with sources lacking `published` listed as undated;
- questions about change over time are answered using `wiki timeline`.

The ingest workflow SHALL include copying `published` from the raw file (leaving it empty and telling the human when the raw file has none) and adding a Timeline entry. The query workflow SHALL direct time-related questions to `wiki timeline` and `--since`/`--until`/`--sort`. The lint workflow's backfill step SHALL report missing authors and dates from `wiki source-meta --all` to the human as a checklist, with suggested values, and SHALL NOT edit any page.

#### Scenario: Schema mentions chronology
- **WHEN** `AGENTS.md` is inspected after init
- **THEN** it documents `published` on source pages, dated claims, Timeline sections and `wiki timeline`

#### Scenario: Workflows handle dates
- **WHEN** the rendered ingest, query and lint workflows are inspected
- **THEN** ingest copies `published` and adds a Timeline entry, query mentions `wiki timeline`, and lint reports missing `published` without editing pages

#### Scenario: No guessing dates
- **WHEN** the rendered ingest workflow and `AGENTS.md` are inspected
- **THEN** they say that when the raw file records no `published`, the field stays empty and the human is told, and they forbid inferring, looking up or changing dates
