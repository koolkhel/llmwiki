---
description: Capture a URL, text file or saved web page and fold it into the wiki
argument-hint: <url | path to .txt/.md/.html> [focus or notes]
---

Ingest this source into the wiki, following `AGENTS.md`: $ARGUMENTS

If no source was given, run `wiki status --json` and offer to ingest the pending
raw sources it lists. Skip step 1 for those, since they are already captured.

1. **Capture.** Run `wiki add-source "<url or path>" --json`.
   - Exit 2: stop and report `error.message`. Do not fall back to a web-fetch
     tool or pasting. If a URL failed with `http_error` (e.g. 401/403) or
     `extraction_failed`, the site probably blocks automated fetching: ask the
     human to save the page from their browser (as "Webpage, Complete" or HTML)
     and give you the `.html` path, then capture that file instead.
   - For a saved `.html` page, check `url_source`. If it is null, or the
     recorded URL looks wrong (e.g. a homepage), ask the human for the real URL
     and re-run with `--url <url>` after they delete the wrongly captured raw
     file.
   - If `duplicate_of` is set and `status` is `ingested`, tell the human it is
     already in the wiki and stop, unless they asked for a re-read.
   - Otherwise continue with the returned `path`.
2. **Read** the raw file at `path` in full.
3. **Orient.** Read `index.md`. For the main entities and concepts in the source,
   run `wiki search <terms> --json` and read the pages you find.
4. **Source page.** Run `wiki new-page --type source "<source title>" --raw <path> --json`
   and write it: one-line `summary`, key points, notable data or short quotes,
   and a "Touches" section linking every page you create or update below.
   **Authors:** copy the raw file's `authors` into the source page as
   `authors: ["[[Name]]", ...]`, in order. For each author, find the person page
   (`wiki search --author "<Name>" --json`, `wiki search "<Name>" --type entity --json`)
   or create it (`wiki new-page --type entity "<Name>" --json`, `tags: [person]`),
   and add this source to its **Articles** section. If the raw file has no
   `authors`, look for a byline in the text and ask the human rather than guess.
5. **Update the wiki.** Typically 5–15 pages:
   - Update existing entity/concept pages with the new information. Add the
     source page to their `sources:`, bump `updated`, and cross-link.
   - Create pages (with `wiki new-page`) for significant new entities and
     concepts. Don't create pages for trivia.
   - Record contradictions with existing claims as described in `AGENTS.md`.
6. **Check.** Run `wiki lint --json` and fix every `error`. Fix `orphan` and
   `empty_summary` warnings on pages you touched.
7. **Index and log.** Run `wiki index --json`, then
   `wiki log ingest "<source title>" --detail "<pages created/updated>" --json`.
8. **Commit** the vault: `git add -A && git commit -m "ingest: <source title>"`.

Finish with a short report: what the source says, pages created or updated,
and any contradictions or open questions it raised.
