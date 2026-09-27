## Why

`wiki search` matches raw substrings, which works poorly for Russian, where words take many case, number and verb-tense forms. A query for `кошка` misses pages that say `кошек` or `кошкой`, `люди` never finds `человек`, and `шёл` never finds `идти`. The current accent-folding also merges `й` with `и`, so `мой` and `мои` look identical. Claude compensates by guessing stems, but it misses things. That matters for a wiki whose value depends on finding the existing page before creating a near-duplicate.

A spike compared Snowball stemming (the same algorithm tantivy uses for Russian) with dictionary lemmatization (pymorphy3). Snowball missed `кошек`, `люди` and `шёл`, and falsely merged `стать`/`статья` and `вести`/`весть`. pymorphy3 handled all of them correctly.

## What Changes

- Search matches words by **lemma** (Russian, via a morphological dictionary) or by **stem** (English, via Snowball), in addition to today's matching.
- Matches are ranked in three tiers: **exact word** > **same lemma/stem** > **substring**. Today's substring matching is kept as the lowest tier, so nothing that matches today stops matching. The field ranking (title > summary/tags > body) still applies first.
- Each result reports how it matched (`match: exact | lemma | substring`).
- New `--exact` option: match whole words literally (after case and `ё`/`е` folding) with no lemma or substring matching. Useful for names and codes.
- Folding fix: Cyrillic `й` stays distinct from `и`, and `ё` still matches `е`. Latin accents are still ignored (`cafe` matches `Café`).
- A disposable per-vault lemma cache under `.llmwiki/cache/` keeps repeated searches fast. It ignores itself in git, so vaults created before this change also leave it out, and deleting it never changes results.
- The vault templates (`CLAUDE.md`, `/query`, `/ingest`) mention that search understands word forms and describe `--exact`.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `wiki-navigation`: the "Search pages" requirement gains word-form matching, match tiers, the `match` field, `--exact`, and the `й`/`ё` folding rules. A new requirement covers the disposable search cache.

## Impact

- New runtime dependencies: `pymorphy3` (with its roughly 15 MB Russian dictionary, `pymorphy3-dicts-ru`) and `snowballstemmer`. Both are pure Python and work offline.
- Code: `search.py` is reworked around a new tokenizer and word-form module. The templates change only in wording.
- Vault: a new `.llmwiki/cache/` directory, created on first search.
- Behaviour: result order can change, because lemma matches now outrank substring matches. The JSON output gains a `match` field. No existing fields are removed.
