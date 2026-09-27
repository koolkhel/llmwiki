## Context

See proposal.md for motivation. Current state (`src/llmwiki/search.py`):
- `fold()` applies NFKD, drops every combining mark (which turns `й` into `и` and `ё` into `е`), then case-folds.
- A term matches if its folded form is a substring of the folded title, summary+tags, or body.
- The score is title 100, summary/tags 10, body 1 per occurrence (capped at 5). Snippets come from a folded-to-original index map.
- There is no index: every `wiki search` call reads and scans all pages. That fits the file-first design (bootstrap design D4) and the expected scale of hundreds of pages.

Spike results (scratch venv, Python 3.14; see the exploration notes):

| | Snowball RU (also what tantivy uses) | pymorphy3 lemmas |
|---|---|---|
| кошка/кошек/кошкой | кошек → "кошек" (miss) | all → кошка |
| люди → человек, шёл → идти | miss | hit |
| false merges стать=статья, вести=весть | yes | no |
| speed | about 10M words/s | about 30k unique forms/s |
| size | 2 MB | about 15 MB dictionary |

On a real ru.wikipedia article (1,071 Cyrillic tokens, 638 unique forms), lemmatization took 21 ms. Without a cache, a few hundred pages (about 60k unique forms) would cost roughly 2 s on every search.

## Goals / Non-Goals

**Goals:**
- Russian word-form matching that handles case, number, tense and irregular (suppletive) forms, plus English stemming.
- Anything that matches today still matches (substring tier).
- Warm searches stay interactive (well under a second at hundreds of pages), without adding a source of truth besides the files.

**Non-Goals:**
- BM25/tf-idf ranking, a full-text index, tantivy or SQLite FTS5. These can be added later on top of the same tokenizer.
- Languages other than Russian and English (their words still get exact and substring matching).
- Synonyms, fuzzy or typo-tolerant matching.
- cp1251 text-file capture (separate change).

## Decisions

### D1. pymorphy3 for Russian, Snowball for English
- Russian: `pymorphy3.MorphAnalyzer()` with `pymorphy3-dicts-ru`. It is the only option in the spike that fixes the case forms users actually hit (genitive plural, suppletive forms). Words missing from the dictionary still get a lemma guessed from their ending (`нейросетями` → `нейросеть`).
- English: `snowballstemmer.stemmer("english")` (Porter2). It is pure Python and uses PyStemmer's C code automatically if that is installed. Irregular English forms (`mice`, `ran`) remain misses, which is acceptable.
- *Alternatives:* Snowball for Russian (misses the main cases). tantivy (same Snowball quality, plus an index lifecycle and a 23 MB wheel). spaCy or Stanza (far heavier, and they need models downloaded).

### D2. Ambiguous words: index every lemma
`morph.parse(w)` returns several parses. The word's lemma keys are the set of all their `normal_form`s (`бегу` → {бег, бежать}, `мой` → {мой, мыть}). The query side does the same. The lemma tier matches when the two sets intersect. This deliberately errs toward extra matches rather than missed ones. The exact tier ranks true hits above them.

### D3. Tokenizer and folding (new module `llmwiki/morph.py`)
- Tokens are maximal runs of `[^\W_]` (Unicode letters and digits), kept with their start and end offsets in the original text so snippets can point at them. A hyphenated compound (`нейро-сеть`) is emitted both as its parts and as the joined form (`нейросеть`).
- `fold(word)`: NFC, then case-fold. Latin letters get NFKD with combining marks removed. Cyrillic letters are left undecomposed, except `ё` → `е`. This fixes the `й` → `и` bug while keeping `cafe` = `Café`.
- `keys(word)`: Cyrillic token → the folded lemmas from pymorphy3 (lemmas also go through `fold`, so `ёж` and `еж` agree). Latin token → the Snowball stem of the folded form. Mixed-script, digit-only or other tokens → the folded form only.
- The substring tier keeps today's behaviour, but uses the new `fold` so that `й` is preserved there too.

### D4. Scoring
For each query term, take the best `field_weight × tier_weight` over all fields and tiers, with field weights title 100, summary/tags 10, body 1 and tier weights exact 3, lemma 2, substring 1. The page score is the sum over terms. This keeps "stronger field first, then stronger tier" for single-term queries: title-substring (100) > summary-exact (30), and summary-substring (10) > body-exact (3). Ties are broken by the number of body occurrences of matching words, then by title and path. Today's "body count × weight" term is dropped from the main score because it could let a body match outrank a summary match. `match` is the weakest tier among the terms' best matches. `--exact` restricts the tiers to exact only.

### D5. Disposable cache: `.llmwiki/cache/lemmas.sqlite`
- SQLite from the standard library. Table `forms(form TEXT PRIMARY KEY, keys TEXT)` holds form → lemma keys, and a `meta` row holds a version string (pymorphy3 version + dictionary version + fold-rules version). On a version mismatch the table is emptied.
- The whole table is loaded into a dict at search start (60k rows loads in tens of milliseconds). Forms missing from it are analysed and written back in one transaction when the search ends.
- On first creation, `wiki search` writes `.llmwiki/cache/.gitignore` containing `*`. Nothing else in the vault changes, and `.gitignore` templates stay untouched.
- Any `sqlite3.Error` or `OSError` falls back to in-memory analysis for that run, without failing the search. With `--json`, a warning is added to the output.
- Only the lemma table is cached. Page tokens are recomputed each run, which is cheap (tokenizing about 1M tokens takes well under a second) and avoids invalidating the cache when pages change.
- *Alternatives:* a JSON file (rewriting all of it on every run, and a partial write can corrupt it), a full inverted index (a second source of truth that goes stale), or no cache (about 2 s per search at scale, and Claude searches many times per ingest).

### D6. Lazy imports
`pymorphy3` is imported only by `wiki search` and loaded once per process, so other commands don't pay for it. Its cold load time gets measured in the tasks. If it is noticeable (over 300 ms), the analyzer is still created only when the query or the pages contain Cyrillic.

### D7. Template wording
The vault `CLAUDE.md` and `/query` template say: "search matches word forms (кошка ↔ кошек, run ↔ running); use `--exact` for names and identifiers; check the `match` field." Existing vaults keep their current files, because `wiki init` never overwrites. This doesn't matter, since the CLI behaviour improves either way.

### D8. Implementation notes and measurements (recorded during apply)
- **Cold pymorphy3 load is 41 ms** (import plus dictionary, offline), well under D6's 300 ms threshold, so the "only when Cyrillic is present" optimisation was not needed. The analyzer is still created lazily on first use.
- **Performance** on a synthetic vault of 300 pages, about 276k tokens, 1.7k real dictionary forms plus 38k generated Cyrillic/Latin forms (no real content), on the author's machine: cold first search **2.66 s** (fills the cache, 3.7 MB); warm search **0.54 s**; three-term warm search **0.60 s**. For comparison, `wiki status` takes 0.14 s. Two optimisations were needed to get below 1 s:
  - a fast path in `fold_with_map` for runs of ASCII/Cyrillic (case-folding one to one), plus `lru_cache` on `fold`;
  - a simple `[^\W_]+` tokenizer regex, with the combining-mark-aware pattern used only when the text actually contains combining marks.
  A property test checks that the fast fold path matches the character-by-character path.
- **Test-data corrections:** `вести`/`весть` and `мыло`/`мыть` really do share lemmas (`вести` is also the plural of `весть`, and `мыло` is a past form of `мыть`), so all-lemmas matching links them, correctly. The "no false merge" tests keep `стать`/`статья` and `лес`/`лесть`.
- **Real-page check** (captured ru.wikipedia "Мемекс", `--raw`): `гипертекстом` matched via lemma (the page has `гипертекст`), `учёный` matched `учёных` via lemma, `микрофильмы`/`устройство` matched exactly, and `машина` (absent from the page) returned nothing.
- Link targets inside markdown links (`[text](https://…/Гипертекст)`) are part of the body text, so they can match and appear in snippets. This is harmless and left as is.

## Risks / Trade-offs

- [Taking every lemma produces unexpected matches (`мой` also matches `мыть`)] → these rank below exact matches, and `match: "lemma"` makes them visible. `--exact` removes them.
- [pymorphy3 guesses wrongly for proper names or unusual words not in its dictionary] → exact and substring tiers still work on names, and the `/query` template tells Claude to try `--exact` for names.
- [The substring tier adds noise for short terms] → it ranks lowest, and this is unchanged from today.
- [A corrupted or locked cache] → errors are caught and the run falls back to in-memory analysis. The cache is safe to delete, and the version key forces a rebuild after upgrades.
- [Changing result order could surprise Claude's habits] → the output keeps its existing fields, and only order plus the new `match` field change.
- [pymorphy3 or its DAWG backend has problems on future Python versions] → it is pure Python (DAWG2-Python), confirmed on 3.14. It sits behind the `morph.keys()` interface, so it could be swapped out.

## Migration Plan

No data migration. After upgrading, the first search in each vault creates `.llmwiki/cache/`. Rolling back means downgrading the package; a leftover cache directory is harmless and ignored by git.

## Open Questions

None blocking. The cold pymorphy3 load time and warm-search latency get measured in the tasks, and may only affect when D6's "Cyrillic only" optimisation applies.
