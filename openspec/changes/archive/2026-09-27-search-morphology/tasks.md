## 1. Dependencies

- [x] 1.1 Add `pymorphy3` and `snowballstemmer` to `pyproject.toml`, reinstall the venv, and verify that `pymorphy3.MorphAnalyzer()` loads offline under the test network guard. Record the cold load time for D6.

## 2. Word-form module

- [x] 2.1 Create `llmwiki/morph.py` with `fold()`: `й` stays distinct from `и`, `ё` becomes `е`, Latin diacritics are stripped, and text is case-folded. Verify with unit tests for `й`/`и`, `ё`/`е`, `Café`/`cafe` and `ß`.
- [x] 2.2 Add `tokenize(text)` returning tokens with their original offsets, plus hyphenated compounds emitted both as parts and joined. Verify with tests covering Cyrillic, Latin, digits, emoji/punctuation boundaries, `нейро-сеть`, and offsets that slice back to the original words.
- [x] 2.3 Add `keys(word)`: all pymorphy3 lemmas for Cyrillic words, the Snowball English stem for Latin words, and the folded form otherwise. Verify with tests for the spike word sets (`кошка`/`кошек`/`кошкой`, `люди`→`человек`, `шёл`→`идти`, `бегу`→{бег, бежать}, `running`/`runs`) and for `стать`≠`статья`.

## 3. Cache

- [x] 3.1 Implement the `.llmwiki/cache/lemmas.sqlite` form→keys cache: bulk load, write-back of new forms in one transaction, a version key that clears it on mismatch, and a self-`.gitignore` containing `*`. Verify with tests that a second run analyses no forms, a version change clears the table, and `git status` stays clean in a git vault.
- [x] 3.2 Make cache failures non-fatal: fall back to in-memory analysis on `sqlite3.Error`/`OSError`, with a warning in the JSON output. Verify with tests for an unwritable cache directory and a corrupted database file, both of which must return correct results with exit code 0.

## 4. Search rework

- [x] 4.1 Rework `search.py` to use the three tiers (exact, lemma, substring) per field, the D4 scoring, the `match` field (weakest tier needed), and snippets around the first matching token. Verify that the existing search tests still pass and that new tests cover each tier and the ordering rules (field first, then tier).
- [x] 4.2 Add a `--exact` option to the CLI that restricts matching to the exact tier. Verify with the spec's exact-mode scenario (`кошка` vs `кошек`).
- [x] 4.3 Apply the same matching to `--raw`. Verify with a test where a raw source containing only `людей` is found by `человек`.
- [x] 4.4 Add a test for every scenario in the delta spec (Russian case forms, irregular forms, English stems, exact outranks lemma, substring kept, `й` is not `и`, `ё` matches `е`, exact mode, cache deletion gives identical results), all passing.

## 5. Templates and docs

- [x] 5.1 Update the vault `CLAUDE.md` and `/query` templates per D7 (word-form matching, `--exact` for names, the `match` field), and add a line to the README. Verify that `test_init` still passes and the new wording is present.

## 6. Verification

- [x] 6.1 Performance check on a synthetic vault of about 300 generated Russian/English pages (no real content): measure cold and warm `wiki search` time. Verify that warm searches take under 1 s, and record both numbers in design.md.
- [x] 6.2 Manual check in the scratch vault with the real ru.wikipedia capture: `wiki search` for inflected forms of words in the article returns it with `match: "lemma"`. Record the result.
