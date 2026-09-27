---
description: Upgrade this vault's schema and workflows to the installed wiki version, merging your edits
argument-hint: [notes about customisations to keep]
---

Upgrade this vault's template files (the schema and the workflows),
following `AGENTS.md`. Never touch `raw/`, `wiki/`, `index.md` or `log.md`.
Notes from the human: $ARGUMENTS

1. **Plan.** Run `wiki upgrade --dry-run --json`. Summarise it for the human:
   files to create, update or delete, and **conflicts** (files the human edited).
   Wait for their OK. If there are warnings about uncommitted changes, suggest
   committing first.
2. **Apply.** Run `wiki upgrade --json`. Untouched files are updated. For each
   edited file, the new template is written next to it as `<path>.new`.
3. **Merge each conflict** (`action: "conflict"`): read the human's file and
   its `<path>.new`, and write a merged version that
   - keeps every customisation the human made (their own sections, rules,
     wording, extra lines) exactly, and
   - adopts what the new template adds or changes (new sections, renamed
     commands, updated rules), reconciling overlaps in the human's favour.
   Show the human what changes relative to their file, apply it once they
   approve, then delete `<path>.new`.
4. **Renamed files** (`action: "kept"`, with `replaced_by`): the human edited an
   old file that has since been renamed. Offer to carry those edits into the
   `replaced_by` file (merge as in step 3), then delete the old file.
5. **Check.** Run `wiki lint --json`. No `template_merge_pending` findings should
   remain, and there should be no new errors. Run `wiki status --json`: templates
   should be up to date.
6. **Commit** the vault: `git add -A && git commit -m "upgrade: vault templates"`.
7. Tell the human to **restart the agent session** so new or renamed workflows
   load. The workflows, as Claude Code / Kimi Code commands:
   - ingest: `/wiki-ingest` / `/skill:wiki-ingest`
   - query: `/wiki-query` / `/skill:wiki-query`
   - lint: `/wiki-lint` / `/skill:wiki-lint`
   - upgrade: `/wiki-upgrade` / `/skill:wiki-upgrade`
