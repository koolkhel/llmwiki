---
description: Health-check the wiki (structural plus semantic) and fix what you can
argument-hint: [area or tag to focus on]
---

Health-check the wiki, following `AGENTS.md`. Focus: $ARGUMENTS

1. **Structural.** Run `wiki lint --json`.
   - Fix every `error`: dead links (create the page with `wiki new-page`, or
     correct the link), frontmatter, type/folder mismatches, duplicate names
     (merge the pages, or disambiguate one title), and bad filenames (rename to
     the suggested name and update links).
   - `raw_modified` or `raw_missing`: do **not** "fix" raw files. Report them
     to the human, who can restore them from git.
   - Warnings: link orphans from related pages, and fill empty summaries.
   - Mention `pending_source` items and offer to run the **ingest** workflow on
     them (`/wiki-ingest` in Claude Code, `/skill:wiki-ingest` in Kimi Code).
2. **Semantic.** Read across the wiki (or the focus area) and look for:
   - contradictions between pages that are not yet flagged,
   - claims with no source, or stale claims superseded by newer sources,
   - concepts or entities that are mentioned repeatedly but have no page of their own,
   - missing cross-links between clearly related pages,
   - bloated pages that should be split, or near-duplicates that should be merged.
   Fix what is clear-cut. List anything that needs the human's judgement.
   **Metadata check (report only):** run `wiki source-meta --all --json` and
   list each item for the human as a checklist: raw file, source page, what is
   `missing`, and the suggested `authors`/`published` re-derived from the
   stored original. The human verifies and enters these themselves: do **not**
   edit source pages, person pages or Timeline sections for these items. Items
   without a source page are pending sources; mention them too. Also look for
   duplicate person pages (name variants) and merge them, keeping `aliases`.
3. Re-run `wiki lint --json` until there are no errors, then run `wiki index --json`.
4. **Log.** Run `wiki log lint "<one-line result>" --detail "<what changed / what needs a decision>" --json`.
5. If anything changed, commit: `git add -A && git commit -m "lint: <summary>"`.
