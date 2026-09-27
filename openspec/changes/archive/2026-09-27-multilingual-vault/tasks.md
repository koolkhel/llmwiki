## 1. Language setting

- [x] 1.1 Add `llmwiki/languages.py` (the D1 table) and `vault.language()` (tomllib; None when unset; `invalid_language` for an unknown code or bad TOML). Verify with unit tests: unset, each supported code, an unknown code, and malformed TOML.
- [x] 1.2 Template placeholders per D2 (`{{language_rule}}`/`{{language_section}}` in `AGENTS.md`, `{{language_line}}` in `llmwiki.toml`), `planned_files(..., language)`, and `wiki init --language` per D4. Verify with tests: the unset rendering is byte-identical to the current `AGENTS.md` template; `--language en` writes the TOML key and the Language section with all five rules; `--language xx` exits 2 and creates nothing.

## 2. Upgrade and registry

- [x] 2.1 Make `upgrade.current_files(language)`/`plan()` use `vault.language()`, never writing `llmwiki.toml`. Update `scripts/known_hashes.py` to register the renderings for all languages (D3), and run it. Verify with tests: an untouched unset vault switched to `language = "en"` upgrades `AGENTS.md` to the English rendering with `llmwiki.toml` byte-identical; an untouched `--language ru` vault is `unchanged`; the registry-completeness test covers every language.

## 3. Search: scripts

- [x] 3.1 Implement the D5 fold change (drop only Combining Diacritical Marks blocks; bump `FOLD_VERSION`) and the mark-aware tokenizer (lazy mark class). Verify with tests: Hindi `प्रशिक्षित`/`बड़े` stay whole and distinct from `परशिकषित`/`बडे`; precomposed and decomposed nukta fold equal; Russian stress marks are still dropped; `Café` still equals `cafe`; the fast/slow fold equivalence test is extended with Devanagari and CJK. Measure the mark-class build time.
- [x] 3.2 CJK bigrams on the document and query side per D5. Verify with tests: `模型`/`训练` match `大语言模型的训练需要大量数据` at the exact tier; a single ideograph matches via substring; snippets point at the bigram's position.

## 4. Search: aliases

- [x] 4.1 `Page.aliases` and the aliases in the title field (D6), and author matching through linked person-page aliases (D7). Verify with the spec scenarios: `языковая модель`, `大语言模型` and `भाषा मॉडल` find the English `Large language model` page as a title match; `--author 李飞飞` finds a source by `[[Fei-Fei Li]]`; a string (non-list) `aliases` also works.

## 5. Templates, docs, verification

- [x] 5.1 Write the Language section text (D8) and the ingest-workflow line, and update the README (the `--language` option, switching a vault, the multilingual guidance). Verify that the init/upgrade tests pass and the agent-neutral naming test passes. Re-run `scripts/known_hashes.py`.
- [x] 5.2 End to end on a synthetic four-language vault (made-up pages with English titles, and aliases in ru/zh/hi): `wiki init --language en`, pages created, then queries in each language find the right pages, and the search timing on the 300-page perf corpus stays within 10% of before. Then take a copy of an unset vault, set `language = "en"`, and run `wiki upgrade`. Record the results in design.md. Commit, push, and confirm CI passes.
