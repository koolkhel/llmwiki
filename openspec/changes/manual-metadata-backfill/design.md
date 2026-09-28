## Context

See proposal.md. The current template wording to change:
- `workflows/ingest.md`, step 4: "If the raw file has no `authors`, look for a byline in the text and ask the human rather than guess.", and "**Date:** … If there is none, look for a date in the text and ask the human."
- `workflows/lint.md`, semantic step: "**Metadata backfill:** run `wiki source-meta --all --json` … For `authors`, add them to the source page … For `published`, set the source page's `published: YYYY-MM-DD` and add or fix its lines in the relevant Timeline sections."
- `vault/AGENTS.md`: the Authors section says "If a raw file has none, check the text for a byline and ask the human before leaving it empty."; the Chronology section says "Copy the date into the source page …".

`wiki source-meta` reads only `raw/.orig/` locally, so no CLI change is needed for "never look them up". Web lookups for *sources* are already forbidden by the schema. This change extends that rule to metadata.

## Goals / Non-Goals

**Goals:** metadata on source pages is either copied deterministically from the raw file or entered by the human. The agent reports gaps and never fills them.

**Non-Goals:**
- CLI changes;
- removing the lint warnings (they stay as the human's to-do list);
- changing how capture extracts metadata into raw files (that is deterministic and stays).

## Decisions

### D1. One rule, stated once in `AGENTS.md` and applied in the workflows
A short rule under Authors and under Chronology: "`authors`/`published` on a source page come **only** from the raw file or from the human. Never infer them from the text, never look them up, and never change a value that is already set. If the raw file has none, leave the field empty and tell the human." The Timeline guidance adds "list sources without `published` as `undated`".

### D2. Ingest: copy or leave empty
Step 4 copies `authors` and `published` from the raw file. When either is missing, the agent says so in its final report ("no author/date recorded; left empty") and does nothing more. The author-page creation still happens for authors the raw file does record.

### D3. Lint: report-only backfill
The step becomes: "**Metadata check (report only):** run `wiki source-meta --all --json` and list each item for the human (raw file, source page, what is `missing`, and the suggested `authors`/`published` from the stored original) so they can verify and enter it themselves. Do not edit source pages, person pages or Timeline sections for these items." It stays within the semantic step, and the lint log entry records how many items were reported.

### D4. Hash registry and upgrade
The template edits change the rendered `AGENTS.md` (all languages) and the ingest and lint workflows (both agents), so `scripts/known_hashes.py` is re-run. Untouched vaults are updated by `wiki upgrade`, and customised ones get `.new` files to merge.

## Risks / Trade-offs

- [Source pages stay undated or unattributed longer] → intended. `missing_*` warnings and the lint report keep them visible, and `wiki timeline` shows them as undated.
- [The agent ignores the rule] → the rule is stated in both the schema and the workflows, and tests assert the wording, including the absence of the old "look for a byline/date in the text" instructions.

## Migration Plan

`wiki upgrade` in each vault (and `/wiki-upgrade` if `AGENTS.md` is customised). Nothing in existing pages changes.

## Open Questions

None.
