## 1. Author extraction

- [x] 1.1 Implement `fetch._jsonld_authors(html, url)` per D1: parse all JSON-LD blocks (lists, `@graph`, single objects, invalid blocks skipped), choose the main article object by type and URL, and read `author` as a string, object or list, in order. Verify with synthetic unit tests: list/`@graph`/single object, several article objects with URL matching, string vs Person vs Organization authors, invalid JSON, and a BreadcrumbList-only page.
- [x] 1.2 Implement `fetch._authors()` with the D1 precedence (JSON-LD, trafilatura `author` split on `;`, mcmetadata `other.authors`), normalisation and de-duplication, and add `authors` to `FetchedPage` from `extract()` (one mcmetadata call with `include_other_metadata=True`). Verify with tests that a synthetic page with JSON-LD plus a sidebar widget of other authors yields only the article's author, that the meta-tag fallback works, that a multi-author order is kept, and that there are none when nothing is present. Measure the extraction-time increase on the synthetic 300-page perf corpus or a saved page, and record it.

## 2. Capture

- [x] 2.1 Write `authors` (when non-empty, after `title`) in URL and saved-page captures, and in `.md` captures from `original_frontmatter` `author`/`authors` with `[[…]]` stripped. Verify with capture tests for each kind, including Web Clipper-style `author: "[[Jane Doe]]"`, and a `.txt` capture having no `authors`.

## 3. Backfill command

- [x] 3.1 Add `wiki source-meta <raw>` and `--all` per D3 (JSON and text output, `derivable`, source page path or null). Verify with tests: an older-style raw without `authors` but with a JSON-LD `.orig` is listed with derived authors; an already-attributed source page is not listed; a `.txt` raw reports `derivable: false`; and a vault snapshot is byte-identical before and after.

## 4. Lint

- [x] 4.1 Add the `missing_authors` warning and `authors`-must-be-a-list validation per D4. Verify with lint tests in the existing one-defect-per-test style (warning present, absent when attributed, `frontmatter_invalid` for a string `authors`), and that a fresh vault still lints clean.

## 5. Search

- [x] 5.1 Add `--author` per D5: optional query terms, author-token matching with the exact and lemma tiers, support for `--raw` and `--exact`, and title sort when there are no terms. Verify with tests for each spec scenario, including the declined form `Колдина` matching `Владимир Колдин` and wikilink/alias forms in `authors`.

## 6. Templates and docs

- [x] 6.1 Update `AGENTS.md` (the `authors` field and an "Authors" subsection), the ingest workflow (an author-page step) and the lint workflow (the `source-meta --all` backfill) per D6, plus the README command table (`source-meta`, `--author`). Verify that the vault-init delta scenarios pass as tests on rendered output and that the agent-neutral reference test still passes.

## 7. Verification

- [x] 7.1 Real-page check in a scratch vault: `wiki add-source https://rossaprimavera.ru/article/7c7b02cb` records `authors: [Владимир Колдин]` (not Максим Карев); `wiki search --author Колдина --raw` finds it; and a copy of an older-style raw without `authors` next to its `.orig` is reported by `wiki source-meta --all`. Record the results in design.md. Push, and confirm CI passes.
