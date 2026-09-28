## Why

The user wants to verify authors and publication dates on existing sources personally, when they have time, rather than having the agent fill them in. Today:
- the lint workflow's backfill step makes the agent **edit** source pages with values from `wiki source-meta --all`;
- the ingest workflow and the schema tell the agent to look for a byline or date in the text when the raw file has none.

Both put the agent's judgement into metadata that the user wants to control.

## What Changes

- **Only two sources of truth for source-page metadata:** `authors` and `published` on a source page come only from the raw file (copied at ingest) or from the human. The agent never infers them from the text, never looks them up (on the web or elsewhere), and never changes values that are already set.
- **Ingest:** copies `authors` and `published` from the raw file when present. When either is missing, it leaves the field empty and tells the human, without guessing from the text.
- **Lint workflow:** the backfill step becomes **report-only**. It runs `wiki source-meta --all --json` and presents the items as a checklist for the human (raw file, source page, what is missing, suggested values), and edits nothing.
- **`AGENTS.md`:** the Authors and Chronology sections state the rule above. The Timeline guidance says to list sources without a date as "undated" rather than dating them.
- **Unchanged:** the CLI (`source-meta` already only reads local stored originals), and the `missing_authors`/`missing_published` lint warnings, which remain the human's to-do list.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `vault-init`: "Schema covers authorship" and "Schema covers chronology" change from agent backfill (and asking the human for a guess) to report-only backfill and empty-when-unknown.

## Impact

- Templates only: `vault/AGENTS.md`, `workflows/ingest.md`, `workflows/lint.md`; `templates/known_hashes.json` regenerated; README wording; tests.
- Existing vaults get the new wording through `wiki upgrade` (and `/wiki-upgrade` for a customised `AGENTS.md`).
