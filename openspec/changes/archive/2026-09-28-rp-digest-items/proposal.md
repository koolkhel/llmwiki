## Why

The weekly news digests of the newspaper «Суть времени», published on rossaprimavera.ru (ИА «Красная Весна»), consist of short news items. Each item has a dateline (place, date, outlet), text quoted from that outlet and, sometimes, the editorial board's comment. The author wants these items in the `rp-news` vault as dated, attributed and searchable background for AiWriter. Today capture flattens a digest into one body, and the editorial comment becomes an ordinary paragraph that reads as if the quoted outlet said it. The whole issue also gets one date (the issue's), although its items are dated days earlier.

## What Changes

- New read-only command `wiki source-items-rp <raw>`. It is specific to this newspaper's digest format and parses the raw file's stored original HTML into items. For each item it gives the section, place, date (with the year inferred from the issue date), outlet, verbatim quoted text and verbatim editorial comment. It also gives the issue's title, number and date. It exits 1 when the page is not in the digest format and never guesses.
- `wiki add-source` marks raw files captured from rossaprimavera.ru digest pages with `format: rp-digest` in their frontmatter. This works for a URL or a saved `.html`, and tells the agent to use `source-items-rp` rather than read the flattened body.
- Digests are ingested as one source page per item plus a hub source page for the issue, all with `raw:` pointing at the same raw file. New optional frontmatter fields on source pages:
  - `item` (the item's number in the digest);
  - `outlet` (who reported the fact);
  - `via` (the issue hub page);
  - `commentary` (true when the item carries an editorial comment).
- `wiki search --commentary` restricts results to pages with `commentary: true`. Search and timeline results show `outlet` when present.
- `wiki lint` checks digest coverage:
  - every item of an `rp-digest` raw file has a source page;
  - each item page's `published` and `commentary` agree with the parsed item.
- The ingest workflow and the `AGENTS.md` schema get a short rp-digest branch: it names the item page layout, keeps the quote and the comment verbatim under separate headings, and attributes the comment to the newspaper, never to the outlet.
- No change for any other source. Only new raw files get `format: rp-digest`; nothing is backfilled.

## Capabilities

### New Capabilities
- `rp-digest`: parsing «Суть времени» digests from rossaprimavera.ru into items, the item/hub page model, and how the schema and workflow treat items and editorial comments.

### Modified Capabilities
- `source-capture`: capture records `format: rp-digest` for recognised digest pages.
- `wiki-navigation`: search gains `--commentary`, and search and timeline results carry `outlet`.
- `wiki-lint`: new `rp_item_missing` and `rp_item_mismatch` findings, and the frontmatter types of `item`, `outlet`, `via` and `commentary` are checked.

## Impact

- Code:
  - new `src/llmwiki/rpdigest.py` (parser; uses the existing BeautifulSoup dependency);
  - `sources.py` (format marker);
  - `cli.py` (new command, search option);
  - `search.py`, `timeline.py`, `lint.py`, `pages.py` (field types).
- Templates:
  - `templates/vault/AGENTS.md` for all languages;
  - `templates/workflows/ingest.md`;
  - new hashes appended to `templates/known_hashes.json`, so `wiki upgrade` brings existing vaults forward.
- Tests: synthetic digest HTML fixtures with invented places, outlets and events, and no network.
- No new dependencies. No change to raw immutability, capture of other sites, or existing page fields.
- Follow-up outside this repo (AiWriter): configure the `rp-news` vault and decide how editorial comments may be used in the back section.
