## Context

See proposal.md for motivation. Current state:
- `fetch.extract()` builds a `FetchedPage` (title, body, URLs, published, language, extractor), and nothing records authors. `sources.capture_url` and `sources.capture_saved_html` write raw frontmatter from it; `capture_file` handles `.txt`/`.md`, keeping `.md` frontmatter as `original_frontmatter`.
- Raw files are immutable (spec), and `raw/.orig/<stem>.html` keeps the page for URL and saved-page captures.
- `search.py` builds `_Doc` objects with title, meta (summary+tags) and body fields, matched in three tiers via `morph.Analyzer`.
- `lint.py` walks pages and raws; `pages.Page.problems()` validates frontmatter types.

Spike on https://rossaprimavera.ru/article/7c7b02cb (fetched to scratch, read-only):
- The response is `Content-Encoding: gzip` even without `Accept-Encoding` (a plain `curl` got binary). `requests` decodes it, so capture is unaffected. This only explains the confusing first probe.
- The author appears **three times**: (1) the byline `<a href="/authors/vladimir-koldin" class="author">Владимир Колдин</a>`; (2) a sidebar widget for *another* article, "Максим Карев, Владимир Колдин" (a trap for naive `class="author"` scraping); (3) JSON-LD: one block holding `[BreadcrumbList, NewsArticle]`, where the `NewsArticle` has `"author":[{"@type":"Person","name":"Владимир Колдин",…}]`.
- The current capture gives the title, `published 2026-08-02`, `language ru` and a 2,027-word body, but the byline is **not** in the body.
- `trafilatura.bare_extraction(...)["author"]`, `trafilatura.metadata.extract_metadata(...).author` and `mcmetadata.extract(..., include_other_metadata=True)["other"]["authors"]` all return `Владимир Колдин`, and none of them picked up Карев.

## Goals / Non-Goals

**Goals:**
- Never lose an author the page states: capture it, carry it into the wiki as a person, and warn when it's dropped.
- Backfill for existing captures without touching raw files.
- Find everything by an author, including declined name forms.

**Non-Goals:**
- Author disambiguation beyond the existing title rules (`Name (role)`), and a person registry or authority data (VIAF, Wikidata).
- Rewriting raw files, or adding `authors` to them after the fact.
- Extracting authors from `.txt` or free text. The agent asks the human instead.
- Changing link resolution to honour Obsidian `aliases` (links always target the canonical page name).

## Decisions

### D1. Extraction order: JSON-LD > trafilatura > mcmetadata (> `.md` frontmatter)
- **JSON-LD** is the publisher's explicit statement, and it is scoped to the article object, so sidebars can't leak in. Parse every `application/ld+json` block, accepting a list, `@graph` or a single object. Pick the **main article object**: prefer an object whose `@type` (a string or a list) is one of `Article`, `NewsArticle`, `BlogPosting`, `Report`, `ScholarlyArticle`, `ReportageNewsArticle`, `OpinionNewsArticle` or `AnalysisNewsArticle`. If there are several, prefer one whose `url`/`@id`/`mainEntityOfPage` matches the page URL (ignoring the fragment), else take the first. From its `author`: a string becomes a name; an object gives its `name`; a list keeps order. Invalid JSON blocks are skipped.
- **trafilatura** metadata `author`: a string that may join several names with `; `. Split on `;` only, not commas, because "Doe, Jane" is one person.
- **mcmetadata** `other.authors`: a list (from newspaper3k). Its heuristics are noisier, which is why it comes last among HTML sources.
- **`.md` frontmatter** `author`/`authors`: a string or a list, with `[[…]]` stripped (Obsidian Web Clipper writes `author: "[[Name]]"`).
- Normalisation: collapse whitespace, strip, drop empty values and values longer than 200 characters (junk), and remove duplicates case-insensitively while keeping the first occurrence and order. The first source yielding at least one name wins, with no merging across sources, which avoids combining different spellings of one person.

### D2. Where the code goes
`fetch.py`: `_jsonld_authors(html, url)` and `_authors(html, url, meta)`. `FetchedPage` gains `authors: list[str]`. `extract()` calls `trafilatura.bare_extraction(..., with_metadata=True)` once for the author, reusing the already-parsed HTML where the API allows. It calls `mcmetadata.extract(..., include_other_metadata=True)` once, replacing the current call without that flag, so there is no extra parse. `sources.py` writes `authors` after `title` in the frontmatter when it is non-empty, for URL, saved-page and `.md` captures.

### D3. `wiki source-meta`: derive, don't store
`wiki source-meta <raw>` runs `fetch.extract_saved(orig_bytes, url_hint=recorded original_url)` on the `.orig` file offline, and prints `{path, recorded: {...}, derived: {...}, derivable}`. `--all` iterates over the raw files. For each, the candidate authors are the recorded `authors` if present, else the derived ones. A file is listed when the candidates are non-empty and its source page (via `ingested_by`) lacks `authors`, or when it isn't ingested yet (source page null). It is read-only, which a test asserts by snapshotting the vault. Cost is one extraction per `.orig`, about 50–150 ms each, so it is intended for occasional backfill, not every lint.

### D4. Lint `missing_authors` compares against raw frontmatter only
Lint stays fast and deterministic: it reads raw `authors` and doesn't re-extract. Its rule is "raw has authors, and the source page's `authors` is missing or an empty list". Comparing names against the linked person pages would be brittle, because of disambiguated titles and aliases, and `dead_link` already covers broken author links. Older raws without `authors` are covered by the lint *workflow* running `source-meta --all`. `Page.problems()` adds "`authors` must be a list" when the key is present.

### D5. `--author` matching
An author entry is a string, possibly `[[Name]]` or `[[Name|alias]]`, of which only the target `Name` is used. The query and each author name are tokenised (`morph.tokenize`), and every query token must match some token of **one** author name via the exact tier or the lemma tier (`Analyzer.keys`), or only exact with `--exact`. pymorphy3 lemmatises Russian surnames (`Колдина` → `колдин`), which a task verifies. Only pages that have an `authors` key are candidates, which in practice means source pages, and raw files with `--raw`. When there are no query terms, results are sorted by title, with `match` set to the author's tier. With terms, the normal scoring applies within the author filter. The CLI's `query` argument becomes optional, and `empty_query` is raised only when neither terms nor `--author` are given.

### D6. Schema and workflow wording
- `AGENTS.md`: the frontmatter block shows `authors:` for source pages. A new "Authors" subsection covers: record authors from the raw file; one entity page per person (`wiki new-page --type entity "<Name as written>"`, `tags: [person]`); an "Articles" list on that page linking the source pages; attributing claims ("According to [[Name]] …"); `aliases:` for variants such as "В. Колдин"; and asking the human when authorship is unknown.
- Ingest workflow: after the source page is created, "Authors: for each name in the raw file's `authors`, find or create the person page and link both ways". If the raw file has none, check the body and ask.
- Lint workflow: in the semantic step, "run `wiki source-meta --all --json` and add missing authors to source pages".
- Workflow references stay agent-neutral.

### D7. Verification and implementation notes (recorded during apply)
- **Extraction cost** is small: JSON-LD parsing plus trafilatura's `extract_metadata` add about 7 ms on the rossaprimavera page (37 ms total extraction) and about 19 ms on the saved gatesnotes page (121 ms). mcmetadata's `include_other_metadata=True` adds 0–4 ms. The real pages yield `Владимир Колдин` and `Bill Gates`.
- **Real page** (scratch vault): `wiki add-source https://rossaprimavera.ru/article/7c7b02cb` records `authors: [Владимир Колдин]`, with no sidebar name (Максим Карев) anywhere in the frontmatter. `wiki search --author Колдина --raw` finds it (`match: lemma`). A copy of the capture with `authors` removed (simulating a pre-change raw), next to its `.orig`, is reported by `wiki source-meta --all` as `Владимир Колдин (derived)`, while the new capture is `(recorded)`.
- **Author matching uses lemmas plus each word's folded form** (a refinement of D5). pymorphy3 reads an unknown surname in -ов as a genitive-plural noun (`Синтетов` → `синтет`), while its declined form lemmatises back to the nominative (`Синтетова` → `синтетов`). Adding the folded form to both sides' keys makes `--author Синтетовым` find `Синтетов`. Real surnames (`Колдина`, `Пупкина`, `Шестерёнкину`, `Ивановой`) match either way. This applies only to author matching; in general search the folded form is already the exact tier.
- Lint: a string `authors` reports both `frontmatter_invalid` and `missing_authors`, because it's the wrong type *and* not a non-empty list. The tests expect both.
- `source-meta --all` re-extracts only raw files that have no recorded `authors` and whose source page lacks them, so vaults captured after this change never pay the extraction cost.

## Risks / Trade-offs

- [JSON-LD states an organisation or the site name as the author] → it is recorded as stated (it is the publisher's claim). The agent can judge whether to create a person page or treat it as an organisation entity; the schema says entity pages for organisations are fine.
- [trafilatura's heuristic author picks up a wrong name on some layouts] → JSON-LD takes precedence when present. Wrong values are visible in raw frontmatter, and the human can correct the source page (raw stays as captured).
- [Name variants create duplicate person pages] → `new-page` duplicate checks and `aliases`, plus `/lint`'s semantic step looking for near-duplicate people.
- [`source-meta --all` is slow on large vaults] → it is only run from the lint workflow, and its output lists only the files that need attention.
- [A second `bare_extraction` call adds time] → measured in a task. If it's significant, the author is taken from the same trafilatura call that produces the body.

## Migration Plan

No data migration. New captures record authors automatically. For existing vaults, run the lint workflow (or `wiki source-meta --all`) to backfill source pages. To get the new ingest and lint wording, delete those workflow files and re-run `wiki init`, as documented in the README.

## Open Questions

None.
