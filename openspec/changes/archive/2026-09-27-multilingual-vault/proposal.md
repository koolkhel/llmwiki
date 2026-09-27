## Why

The user wants one vault (`~/wikis/ai`) fed by Russian, English, Chinese and Hindi sources. The schema currently says "write in the language of the source", so the same concept ends up as a separate page per language, and these pages never link to each other. `wiki search` also can't bridge languages. A probe showed two script bugs as well:
- a run of Chinese text becomes **one token**, so only the weakest (substring) tier ever matches;
- Hindi text breaks into **17 junk tokens** per sentence, because vowel signs end words, and folding drops the virama and nukta (`प्रशिक्षित` becomes `परशिकषित`), which merges distinct words.

The user chose a single wiki language: English throughout for this vault.

## What Changes

- **Wiki language setting:** `llmwiki.toml` gains an optional `language` (a code from a supported list, e.g. `en`, `ru`, `zh`, `hi`, `de`, `fr`, `es`). `wiki init --language <code>` sets it. When it is set, the `AGENTS.md` "Language" section is rendered for that language:
  - write page titles and prose in it, and never translate `raw/`;
  - record the concept's names in every source language and script under `aliases:`;
  - quote the original plus a translation;
  - give people their established name in the wiki language, with the original script as an alias;
  - source pages carry `language` from the raw file.

  When it is unset, the current per-source wording stays. Existing vaults switch by adding the key and running `wiki upgrade`.
- **`wiki upgrade`** reads `language` from `llmwiki.toml` to render the current `AGENTS.md` (it never modifies the file). The hash registry covers the `AGENTS.md` rendering for every supported language.
- **Search:**
  - `aliases` become a searchable field, ranked like the title, so a query in any language finds the concept page;
  - `--author` also matches the `aliases` of the author's person page;
  - Indic scripts: combining vowel signs, virama and nukta stay inside words and are never stripped by folding; only Latin diacritics are removed;
  - Chinese, Japanese and Korean: runs of CJK ideographs are also indexed as overlapping two-character tokens, so a multi-character query matches at the exact tier.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `vault-init`: a new "Wiki language" requirement; "Upgrade vault templates" may read `llmwiki.toml`'s `language` (still never modifies it), and its registry covers every language rendering.
- `wiki-navigation`: "Search pages" gains aliases as a field, author matching via person-page aliases, Indic word handling, and CJK two-character tokens.

## Impact

- Code: `morph.py` (tokenizer, fold, CJK tokens), `search.py` (the aliases field, alias-aware author matching), `scaffold.py` (the `language` value for rendering, `--language`), `upgrade.py` (reading `language`), `vault.py` (reading `llmwiki.toml`), `scripts/known_hashes.py` (renders for all languages), templates (`AGENTS.md` language block, the `llmwiki.toml` template), `cli.py`, README, tests.
- The fold rule changes for non-Latin marks, so `morph.FOLD_VERSION` is bumped, which invalidates the search cache automatically.
- No new dependencies.
