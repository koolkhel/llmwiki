## Context

See proposal.md for the motivation. Current state that shapes the approach:

- **Capture.** `wiki add-source` (URL or saved `.html`) stores the unmodified HTML under `raw/.orig/` and a trafilatura markdown body in `raw/`. trafilatura drops element classes, so in the body a `block_comment` paragraph is indistinguishable from a `quote` paragraph. On the sample issue (№682, 26 items, 7 comments) the comment follows the IAEA quote as a plain line.
- **The digest's markup.** Checked on the live page:
  - `<h3><strong>Section</strong></h3>`;
  - `<p class="block_date">КУРСК, 18&nbsp;сентября&nbsp;— РБК</p>`;
  - `<p class="quote">…</p>`, often with `<em>`;
  - `<p class="block_comment">…</p>`.
  - Interleaved: `div.ad_container` with scripts, and `div.widget.embed` video promos. The site also has markup hidden with inline styles (AiWriter strips it for the same reason).
  - JSON-LD gives the issue date (`2026-09-26T08:41:00+03:00`). The page names «Газета «Суть времени» №682». There are no links to the quoted outlets.
- **Page model today.**
  - Several source pages may already name the same `raw:`. `ingested_by` returns a list, `new-page --raw` doesn't refuse a second page, and status and lint treat a raw file as ingested when any page names it.
  - `published_via` already means "where the date came from", so the outlet needs its own field.
  - `Page.problems()` type-checks optional fields.
- **Templates.** `AGENTS.md` is one English template rendered per language. Workflows are rendered for both agents. Every template change needs `scripts/known_hashes.py` so that `wiki upgrade` recognises the new renderings.

## Goals / Non-Goals

**Goals:**
- A deterministic parser for this one digest format, used by both the CLI command and lint.
- Item pages that the existing date filters, `timeline` and `search` handle without special cases.
- The editorial voice kept separate, verbatim and attributable, from capture through to the page.

**Non-Goals:**
- A general "digest" or site-adapter framework, or per-site configuration.
- Batch or archive capture of past issues.
- Changing the raw body extraction, or rewriting existing raw files.
- Fetching the quoted outlets' originals.
- AiWriter configuration and its rules for using comments in the back section.

## Decisions

### D1. Parse the stored original HTML, not the markdown body
`source-items-rp` and lint read `original_file` with BeautifulSoup, which is already a dependency.
- The classes exist only in the HTML, and the original is stored for every URL and saved-page capture.
- **Alternative rejected:** change capture to emit markers such as `> [!comment]` into the raw body. It would change `sha256` semantics for this site and duplicate the parsing logic. It would also still leave the agent parsing markdown.
- **Alternative rejected:** the agent reads the HTML itself. It is 100 KB per issue, and error-prone.

### D2. A walk in document order, as a small state machine
Iterate over the article body's descendants in order.
- `h3` → current section.
- `p.block_date` → start a new item.
- `p.quote` → append to the current item's quote.
- `p.block_comment` → append to the current item's comment.
- Skipped with their subtrees: hidden elements (`hidden`, inline `display:none` / `visibility:hidden`), `script`, `style`, `iframe`, `.ad_container` and `.widget.embed`. Plain `.widget` is kept, because on the real page `widget article` wraps the article itself.
- Quote or comment paragraphs before the first dateline in a section are attached to no item. They are reported under `unassigned` in the JSON and counted as a problem (exit 1), so a layout change shows up instead of being silently dropped.
- The article body root is the element containing the first `p.block_date`'s ancestors up to the article container. This limits the walk to the article and excludes sidebar widgets such as «gazwidget».

### D3. Dateline grammar
Shape: `^(?P<place>.+?),\s*(?P<day>\d{1,2})\s+(?P<month>genitive month)\s*[—–-]\s*(?P<outlet>.+)$`, after replacing NBSPs.
- Genitive months: января … декабря; `ё` is not involved.
- `outlet` is stripped of surrounding «» and "".
- `place` may contain spaces or hyphens (e.g. «НЬЮ-ЙОРК»).
- A mismatch gives `date: null` and keeps the dateline as written (spec: exit 1).
- **Year:** the issue year, or the previous year if the date would fall after the issue date.
- **Issue date:** the raw file's `published` (JSON-LD at capture), else a re-derivation from the original via the existing `extract_saved`.

### D4. Issue identity
- `title` comes from the raw file.
- `newspaper` and `number` come from the first text matching `«(?P<name>[^»]+)»\s*№\s*(?P<num>\d+)` in the article header. The page writes «Газета «Суть времени» №682» with nested quotes, so the pattern takes the innermost quoted name before `№`.
- Missing values are null, not an error: the hub page title is still derivable from the article title.

### D5. The format marker is decided at capture, by domain plus markup
In `capture_url` / `capture_saved_html`: if the registrable domain of the final or recorded URL is `rossaprimavera.ru` and the HTML contains a `p.block_date`, add `format: rp-digest`.
- The marker is a hint for the agent and the trigger for lint.
- `source-items-rp` itself does not require it. It works on any raw file with an original and refuses by markup (`not_rp_digest`), so a digest captured before this change can still be parsed by hand.

### D6. Page naming and layout (schema text, not code)
- **Hub page:** `Суть времени №<n>`, or the article title when the number is unknown.
- **Item pages:** `<short gist> (<outlet>, <YYYY-MM-DD>)`, for example `Атака дрона на Курскую АЭС (РБК, 2026-09-18)`. Names must be unique, and a gist plus outlet plus date rarely collide. `new-page` still refuses duplicates, and the agent then refines the gist.
- **Item page body:**
  ```
  ## Сообщение (<outlet>, <date>)
  > verbatim quote paragraphs
  ## Комментарий редакции («Суть времени», <issue date>)
  > verbatim comment paragraphs
  ## Touches
  ```
  In a non-Russian vault the headings follow the wiki language, and the quoted text stays in the original.
- `authors` on item pages stays empty: the outlet is not a person. For this reason `missing_authors` must not fire for item pages. The raw file's `authors` (e.g. the rubric «Новости недели») belongs to the hub page only. The lint check will skip `missing_authors` for pages with `item`.
- `missing_published` is naturally satisfied, because item pages have their own `published`.

### D7. Search and timeline changes are small
- `--commentary` is one more pre-filter in `search()`, next to the date filter, reading `meta.get("commentary") is True`.
- `outlet` is copied into results when it is a string.
- Timeline needs no ordering change, because items already carry their own `published`.

### D8. Lint reuses the parser
- Lint parses each ingested `rp-digest` raw file, then builds an item-to-page map from pages with that `raw` and an integer `item`, and emits `rp_item_missing` / `rp_item_mismatch`.
- A parse failure gives one `rp_item_mismatch` on the raw path.
- Parsing costs about 10 ms per issue with html.parser. At one issue a week this stays negligible for years; if needed, cache by `sha256` later.

## Risks / Trade-offs

- **The site changes its markup.** → `not_rp_digest` and the `unassigned` or `date: null` problems make it loud. The parser is small and has fixture tests, so adapting it is cheap.
- **Page count grows by about 27 per issue.** → Accepted (decision B). The index lists them under sources. If the index becomes unwieldy, a later change can group item pages under their hub in `index.md`.
- **The agent paraphrases instead of quoting verbatim.** → The schema requires verbatim blocks. A later lint could compare the page blocks with the parsed item text; it is left out now to keep lint warnings actionable.
- **Editorial comments leak into entity and concept pages as facts.** → The schema rule: any claim from a comment is written as «По мнению редакции «Суть времени» (<issue date>), …» with a link to the item page.
- **Tests must not use real content** (project rule for synthetic data). → Fixtures are hand-written HTML with the same markup and invented places, outlets and events. The live page is used only for a manual smoke check.

## Migration Plan

Additive:
- Existing vaults get the new schema and workflow text through `wiki upgrade`, with hashes appended to the registry.
- The `rp-news` vault is empty, so there are no existing raw files to mark.
- Rollback: revert the commit. Item pages remain valid source pages, and the extra frontmatter fields are ignored.

## Verification (2026-09-28)

Scratch vault (`--language ru`), live page https://rossaprimavera.ru/article/4c87c842:
- **Capture:** the raw file has `format: rp-digest` and `published: 2026-09-26T08:41:00+03:00` (JSON-LD).
- **`wiki source-items-rp`:**
  - the issue parses as «Суть времени» №682;
  - 26 items across 5 sections, exit 0, no problems and nothing unassigned;
  - 6 items carry comments, 7 comment paragraphs in total (item 21 has two);
  - item 3 is `КУРСК`, `2026-09-18`, `РБК`, with the comment «Вообще-то, очень тревожный звонок…»;
  - parsing takes about 50 ms.
- **Implementation finding:** the article on the real page is wrapped in `div.widget.article`, so only `.widget.embed` is skipped (D2).
- **Placeholder test:** a hub page and item pages 3 (commented) and 4.
  - `wiki lint` reports `rp_item_missing` for the other 24 items and no `rp_item_mismatch`. The only `missing_authors` is on the hub, which was deliberately left without the raw file's byline.
  - `wiki search градирня --commentary` returns only item 3, with outlet `РБК`. The same search without the flag returns 3 pages.
