## Context

See proposal.md for motivation. Current state:
- `AGENTS.md` (template) has "Write in the language of the source unless the human asks otherwise" under Writing rules, and no language concept. `llmwiki.toml` holds only `layout_version` and `created`. Nothing reads it beyond vault discovery (which checks that the file exists).
- `scaffold.planned_files(values)` fills `{{layout_version}}`/`{{date}}` placeholders (only `llmwiki.toml` uses them). `upgrade.current_files()` = `planned_files()` minus `llmwiki.toml`/`log.md`, and the registry script hashes exactly that.
- `morph.tokenize`: `[^\W_]+`, with a slower combining-mark-aware pattern only for U+0300–036F. `morph.fold` applies NFKD and drops *every* character with non-zero combining class for non-Cyrillic letters. `FOLD_VERSION = 1` is part of the search-cache version key.
- `search._Doc` fields are title, meta (summary+tags) and body. Author matching uses `authors` entries only.

Probe (synthetic phrases, current code):
- `大语言模型的训练需要大量数据` gives 1 token, so a query for `模型` matches only at the substring tier.
- `बड़े भाषा मॉडल को हिंदी में प्रशिक्षित किया गया` gives 17 tokens (split at every Mc vowel sign: `बड`, `भ`, `ष`, …). `fold` turns `प्रशिक्षित` into `परशिकषित` (virama U+094D, class 9, dropped) and `बड़े` into `बडे` (nukta U+093C, class 7, dropped). `हिंदी` survives only because anusvara has combining class 0.
- Russian and English tokenise correctly.

## Goals / Non-Goals

**Goals:**
- One concept, one page, in the vault's chosen language, findable from any source language.
- Correct word handling for Indic scripts, and usable exact matching for Chinese, without new dependencies.
- Existing vaults are unaffected until they opt in, and can opt in via `llmwiki.toml` plus `wiki upgrade`.

**Non-Goals:**
- Machine translation inside the CLI (the agent translates while synthesising).
- Chinese word segmentation (jieba) and Hindi or Chinese lemmatisation. Bigrams are enough for matching now.
- Automatic alias generation or transliteration (the agent writes aliases).
- A per-page language override (one wiki language per vault).

## Decisions

### D1. Supported languages: a small table
`llmwiki/languages.py` defines `LANGUAGES = {"en": "English", "ru": "Russian", "zh": "Chinese", "hi": "Hindi", "de": "German", "fr": "French", "es": "Spanish"}`. The registry must enumerate every rendering, so arbitrary codes aren't accepted. `vault.language(vault) -> str | None` reads `llmwiki.toml` with stdlib `tomllib`. A missing key or file gives None. An unknown code or unreadable TOML raises `WikiError("invalid_language")`, listing the supported codes.

### D2. Rendering: placeholders in `AGENTS.md` and `llmwiki.toml`
- `AGENTS.md`: the Writing-rules bullet becomes `{{language_rule}}`, and a `{{language_section}}` placeholder goes after "Writing rules".
  - Unset: the rule is the existing sentence and the section is empty. This rendering is byte-identical to today's template, so existing untouched vaults stay `unchanged`, which a test asserts.
  - Set: the rule reads "Write every page in <Name>; see Language." and the section is a "## Language" block with the five spec rules, naming <Name> and showing a frontmatter example with `aliases:`.
- `llmwiki.toml`: a `{{language_line}}` placeholder that becomes `language = "<code>"\n`, or nothing.
- `planned_files(values, language=None)` and `upgrade.current_files(language=None)` take the language. `upgrade.plan()` reads `vault.language()`.

### D3. Registry covers all languages
`scripts/known_hashes.py` adds `current_files(lang)` for `lang in [None, *LANGUAGES]`, and `historical_files()` is unchanged, since older commits had no placeholders. The completeness test checks every language. That is about 8 `AGENTS.md` hashes per release. The obsolete-path computation takes the union of current paths across languages (the same for all).

### D4. `wiki init --language <code>`
It is validated before anything is written (a usage error, exit 2, nothing created), and passed into `planned_files`. `render_text` shows the chosen language. There's no `wiki language` command: switching means editing `llmwiki.toml` and running `wiki upgrade`, which is documented.

### D5. Tokenizer and fold for non-Latin marks (`morph.py`, `FOLD_VERSION = 2`)
- **Mark class:** at first use, build a regex character class of all BMP code points in categories Mn, Mc and Me by scanning `unicodedata.category`. This takes about 10 ms once per process and only happens on the slow path. Tokens are `(?:[^\W_]|<marks>)+`, starting with a letter or digit, so a stray mark doesn't start a word. The fast `[^\W_]+` path stays for text without any marks (checked with a precompiled `<marks>` search). U+0300–036F is a subset of this, so today's stress-mark handling is preserved.
- **Fold:** instead of "drop every combining character after NFKD", drop only marks in the **Combining Diacritical Marks** blocks (U+0300–036F, 1AB0–1AFF, 1DC0–1DFF, 20D0–20FF, FE20–FE2F). These are Latin, Greek and Cyrillic diacritics, including Russian stress marks. Indic, Arabic and other script marks are kept. NFKD is still applied, so precomposed `ड़` (U+095C) and decomposed `ड` + `़` fold to the same string. The ASCII+Cyrillic fast path is unchanged. The fast-versus-slow equivalence property test is extended with Devanagari and CJK characters.
- **CJK bigrams:** a Han run (U+3400–4DBF, 4E00–9FFF, F900–FAFF, and U+20000+ via the `[\U00020000-\U0003FFFF]` range) of length ≥ 2 is emitted as the run token plus its overlapping two-character tokens, each with offsets. On the query side, a Han run of length ≥ 2 is replaced by its bigrams (all of which must match), and a single ideograph stays one term, matching via substring. Every character is a letter (Lo), so `[^\W_]` already keeps runs together; the bigram step works on those tokens.
- The `FOLD_VERSION` bump changes `morph.versions()`, which empties the lemma cache on first use (existing D5 mechanism from search-morphology).

### D6. Aliases in search
`Page.aliases` returns the frontmatter `aliases` (a list, or a single string) cleaned with `fetch.clean_authors` (which removes whitespace noise and `[[…]]` brackets). The title `_Field` is built from `title` plus the aliases joined with ` · `, so aliases rank as title matches. The snippet stays body-based. Raw documents have no aliases.

### D7. Author matching through person-page aliases
At search start, build `aliases_by_key: key(page stem) -> aliases` for all pages. For each `authors` entry that is a wikilink, add the linked page's aliases to the candidate names for that entry, so `--author 李飞飞` matches `[[Fei-Fei Li]]` whose page lists `李飞飞`. Names without a link match as before.

### D8. Schema wording (Language section, set case)
It says:
- this vault's wiki language is <Name>: titles and prose in <Name>, and `raw/` is never translated or edited;
- every concept or entity page lists its names in other languages and scripts under `aliases:`, and ingest adds new ones as sources introduce them;
- quotes are kept in the original with a <Name> translation;
- people are titled with their established <Name> name, with the original script in `aliases`;
- source pages copy `language` from the raw file;
- search finds pages by any alias, so search in any language before creating a page.

The ingest workflow gets one line: "If the vault has a wiki language, write in it, and add the source's terms to `aliases`." It's generic, not language-specific, so the workflow renderings stay the same for all languages.

### D9. Verification and implementation notes (recorded during apply)
- **The unset rendering is byte-identical** to the previous `AGENTS.md` template. This was checked against `HEAD` before committing, not kept as a permanent test, because future template edits will change it legitimately. Existing untouched vaults therefore stay `unchanged` under `wiki upgrade`.
- **Four-language vault** (synthetic, `wiki init --language en`, English pages with ru/zh/hi aliases): every query reached the right English page. `языковая модель`, `大语言模型`, `模型`, `भाषा मॉडल`, `RLHF`, `подкреплением`, `强化学习`, `सुदृढीकरण` and `李飞飞` matched at the exact tier; the declined `языковых моделей` matched at the lemma tier.
- **Switching an existing vault:** adding `language = "en"` to an unset vault's `llmwiki.toml` makes `wiki status` report `1 outdated`. `wiki upgrade` updates only `AGENTS.md` (the Language section appears), `llmwiki.toml` is byte-identical afterwards, and the status is then `up to date`.
- **Performance (300-page corpus):** a same-session A/B test with each version's own warm cache gave 0.55 s before and 0.56 s after (about +2%). The earlier 0.51 s reading was taken while the machine was less loaded. The cold search after the `FOLD_VERSION` bump took 2.6 s (cache rebuild, one-off). Building the mark class takes about 9 ms, lazily, and one `_MAYBE_MARKS` pre-check gates both the mark-aware path and the Han scan, so pure ASCII/Cyrillic text pays nothing extra.
- **Hindi:** `बड़े भाषा मॉडल को हिंदी में प्रशिक्षित किया गया` now gives 9 correct words (it gave 17 fragments before). `fold` keeps the virama and nukta, and precomposed U+095C equals ड + U+093C after folding.
- **Registry:** `historical_files()` skips templates containing `{{` placeholders when replaying git history (raw placeholder text isn't a real rendering). The committed registry is the source of truth for placeholder-era renderings, and the script registers `current_files(lang)` for the unset case and all 7 languages.
- `vault.language()` raises `invalid_language` for an unknown or malformed value. Commands that read it (`upgrade`, `status`, `lint`) therefore fail clearly instead of guessing.

## Risks / Trade-offs

- [Bigrams create false positives: `模型` also matches a longer phrase containing it] → that is the desired containment semantics. Ranking by field and count still applies, and word segmentation can come later.
- [Fold keeping non-Latin marks makes accent-insensitive matching stricter for, e.g., Arabic harakat] → correct for search: those marks change words. Latin-script accents are still ignored.
- [The mark-class build costs time at startup] → it runs lazily and only when the text contains marks; it is measured in the tasks, with a target under 20 ms.
- [An existing vault's customised `AGENTS.md`] → `wiki upgrade` gives a `.new`, which `/wiki-upgrade` merges.
- [The agent forgets aliases] → the schema rule, plus the ingest workflow line. A lint for missing aliases isn't added (it would be heuristic).

## Migration Plan

For the `ai` vault: add `language = "en"` to `~/wikis/ai/llmwiki.toml`, run `wiki upgrade` (and `/wiki-upgrade` if `AGENTS.md` was edited), then re-ingest or `/wiki-lint` to add `aliases` to existing pages. Other vaults change nothing (the unset rendering is byte-identical). The search cache rebuilds automatically after the fold change.

## Open Questions

None.
