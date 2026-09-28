## 1. Parser

- [x] 1.1 Add a synthetic digest fixture under `tests/`. It uses the site's markup and invented content only: two `h3` sections; datelines with an outlet in «» and one without; quotes with `<em>`; two items with comments; one item without; an `ad_container` with a script; a `widget embed`; a `display:none` paragraph; a sidebar widget outside the article; JSON-LD `datePublished`; and «Газета «Суть времени» №123» in the header. Add variants: a January issue with a December dateline, an unparseable dateline, an ordinary article without datelines, and a quote before the first dateline. Verify that the fixture files load in a trivial test.
- [x] 1.2 Implement `src/llmwiki/rpdigest.py`: the document-order walk (D2), the dateline grammar and year inference (D3), issue identity (D4), and text normalisation (NBSP, whitespace, `<em>` → `*…*`). It returns a result with `issue`, `items`, `unassigned` and `problems`, or raises `not_rp_digest` / `no_original` / `no_issue_date`. Verify with unit tests covering every scenario in `specs/rp-digest` ("Parse a digest into items", "Item dates carry the issue's year", "Refuse unknown formats").
- [x] 1.3 Add the `wiki source-items-rp <raw> [--json] [--vault]` command in `cli.py`, with human text of one line per item (`n  date  place — outlet  [comment]`) and exit 1 when there are problems. Verify with CLI tests: the JSON document shape, exit codes 0, 1 and 2 on the fixtures, and that the vault is byte-identical before and after (read-only).

## 2. Capture marker

- [x] 2.1 In `capture_url` and `capture_saved_html`, add `format: rp-digest` when the domain is rossaprimavera.ru and the HTML has `p.block_date` (D5). Verify with capture tests using the fake web and saved-file paths: a digest URL is marked, a same-site article without datelines is not, another domain with the markup is not, and a plain text file is not.

## 3. Page fields, search, timeline

- [x] 3.1 Type-check `item` (positive int), `outlet` and `via` (strings) and `commentary` (bool) in `Page.problems()`. Verify with lint tests: `commentary: "yes"` and `item: 0` give `frontmatter_invalid`, and the valid values are clean.
- [x] 3.2 Add `wiki search --commentary` (with optional terms, a usage error with `--raw`) and `outlet` in search results and timeline entries (D7). Verify with tests for the four `wiki-navigation` scenarios, and that the existing search and timeline tests pass unchanged.

## 4. Lint coverage

- [x] 4.1 Add `rp_item_missing` / `rp_item_mismatch` (D8), and skip `missing_authors` for pages with `item`. Verify with tests: a missing item, a wrong `commentary` flag, a wrong `published`, an `item` out of range, an unparseable original reported once, a pending digest not checked, a complete digest clean, and item pages without authors not warned.

## 5. Schema and workflow

- [x] 5.1 Add an "rp digests" section to `templates/vault/AGENTS.md` covering:
  - the hub and item model;
  - naming;
  - the body layout with verbatim quote and comment headings (D6);
  - the attribution rule for editorial comments («По мнению редакции …»);
  - `--commentary` search.

  Add the `format: rp-digest` branch to `templates/workflows/ingest.md`, covering:
  - `wiki source-items-rp`;
  - the hub page first, then one `new-page` per item with the fields;
  - entity and concept links to item pages;
  - stopping on exit 2;
  - asking about `date: null`;
  - lint coverage.

  Mention `--commentary` in the query workflow. Re-run `scripts/known_hashes.py`. Verify with tests for the two schema/workflow scenarios in `specs/rp-digest`, plus the naming, init and upgrade tests (the registry covers every language rendering).
- [x] 5.2 Update README: the digest workflow, `source-items-rp`, `--commentary`. Verify by reading the rendered README section and confirming the command examples match `wiki --help`.

## 6. Verification

- [x] 6.1 Run the full test suite and confirm it passes.
- [x] 6.2 Real-page check in a scratch vault (not `~/wikis/rp-news`):
  - capture https://rossaprimavera.ru/article/4c87c842 and expect `format: rp-digest`;
  - run `wiki source-items-rp` and expect 26 items, 6 of them with comments (7 comment paragraphs), and the Курск item dated 2026-09-18 from РБК with its comment;
  - create synthetic hub and item pages for two items and check that lint reports `rp_item_missing` for the other 24;
  - check that `wiki search --commentary` finds only the commented page.

  Record the results in design.md, then commit, push, and confirm CI passes.
