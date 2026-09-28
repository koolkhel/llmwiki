---
description: Answer a question from the wiki, with citations
argument-hint: <question>
---

Answer this question using the wiki, following `AGENTS.md`: $ARGUMENTS

1. **Find.** Read `index.md`, then run `wiki search <key terms> --json`. Search
   matches word forms, so try synonyms and related terms rather than
   inflections. Use `--exact` for names and identifiers, and treat
   `match: "substring"` hits as weak. Read the relevant pages and follow their
   links. If the wiki is thin on the topic, also run
   `wiki search <terms> --raw --json` and read the matching raw sources.
   For questions about *when* something was said or how views changed, run
   `wiki timeline "<Page>" --json` (or `--author "<Name>"`) and
   `wiki search <terms> --since … --until … --sort oldest --json`, then answer
   in chronological order with dates. For the editorial board's view on a topic
   (newspaper digests), add `--commentary` to find only items with an editorial
   comment, and attribute those to the newspaper, not to the quoted outlet.
2. **Answer** from what the wiki says. Cite pages inline as `[[Page]]`. Say
   plainly what the wiki does not cover, and where sources disagree. Don't
   present outside knowledge as coming from the wiki; label it if you add any.
3. **File it back** (ask first unless the human already said to). If the answer
   is a synthesis worth keeping:
   - Run `wiki new-page --type analysis "<descriptive title>" --json`, then write
     the answer with its citations and set `summary` and `sources`.
   - Link to it from the most relevant entity or concept pages.
   - Run `wiki lint --json` and fix errors, then run `wiki index --json`.
4. **Log.** Run `wiki log query "<the question>" --json`, adding
   `--detail "Filed as [[<title>]]"` if you filed it.
5. If you filed an analysis, commit: `git add -A && git commit -m "query: <title>"`.
