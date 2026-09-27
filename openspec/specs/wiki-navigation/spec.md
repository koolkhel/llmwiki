# wiki-navigation Specification

## Purpose

Provides the navigation layer of the pattern — a generated catalog (`index.md`), an append-only activity record (`log.md`), page search, and a vault status summary — so Claude can orient itself in the wiki without reading every page.

## Requirements


### Requirement: Generated index
`wiki index` SHALL regenerate `index.md` listing every page under `wiki/`, grouped by type in the fixed order sources, entities, concepts, analyses, each entry being a wikilink followed by the page's `summary`. Within a group, entries SHALL be sorted case-insensitively by title. The file SHALL begin with a notice that it is generated. Output SHALL be deterministic for a given set of pages.

#### Scenario: Index reflects new page
- **WHEN** a new concept page with summary "Short description" is created and `wiki index` is run
- **THEN** `index.md` contains `- [[<title>]] — Short description` under the Concepts heading

#### Scenario: Page without summary
- **WHEN** a page has an empty summary
- **THEN** its index entry is the wikilink alone

### Requirement: Append-only log
`wiki log <operation> <message>` SHALL append one entry to `log.md` of the form `## [YYYY-MM-DD HH:MM] <operation> | <message>` (local time), where `<operation>` is one of `ingest`, `query`, `lint`, `init`, `note`. It SHALL never rewrite or remove existing content. `--detail <text>` MAY add a body paragraph under the heading.

#### Scenario: Greppable entries
- **WHEN** Claude runs `wiki log ingest "Some Article"` three times across a day
- **THEN** `grep "^## \[" log.md` returns the three entries in chronological order and earlier content is unchanged

#### Scenario: Unknown operation
- **WHEN** `wiki log deploy "x"` is run
- **THEN** it fails with a usage error and `log.md` is unchanged

### Requirement: Search pages
`wiki search <query>` SHALL return pages matching all query terms, searching title, summary, tags and body. A term matches a page when it matches in at least one of three tiers:
1. **exact**: the term equals a word of the page after folding;
2. **lemma**: the term and a word of the page share a dictionary form (Russian) or stem (English), taking every possible dictionary form of an ambiguous word into account;
3. **substring**: the folded term occurs anywhere in the folded text.

Folding SHALL be case-insensitive and SHALL ignore Latin diacritics. `ё` SHALL match `е`, and Cyrillic `й` SHALL remain distinct from `и`.

Results SHALL be ranked so that title matches outrank summary/tag matches, which outrank body-only matches. Within the same field, exact matches SHALL outrank lemma matches, which SHALL outrank substring matches.

Each result SHALL include `path`, `title`, `type`, `summary`, `link`, `match`, and a short body snippet around the first matching word. `match` is the weakest tier any query term needed (`exact`, `lemma` or `substring`).

`--type` SHALL restrict results to one page type, `--limit` SHALL cap the count (default 20), and `--raw` SHALL search raw sources instead of wiki pages, with the same matching. `--exact` SHALL disable the lemma and substring tiers.

`--author <name>` SHALL restrict results to pages (with `--raw`: raw files) whose frontmatter `authors` contains a name matching every word of `<name>`, using the exact and lemma tiers (only exact with `--exact`). Wikilink brackets and aliases in `authors` entries are ignored for matching. When `--author` is given, query terms are optional: without them, all pages by that author are returned, sorted by title.

#### Scenario: Title outranks body
- **WHEN** page A has the term in its title and page B only in its body
- **THEN** A is listed before B

#### Scenario: Accent-insensitive
- **WHEN** the query is `cafe` and a page title is `Café culture`
- **THEN** that page is returned

#### Scenario: Russian case forms
- **WHEN** the query is `кошка` and a page's body contains only `кошек` and `кошкой`
- **THEN** that page is returned with `match: "lemma"`

#### Scenario: Irregular Russian forms
- **WHEN** the query is `идти` and a page says only `шёл`, or the query is `человек` and a page says only `люди`
- **THEN** that page is returned

#### Scenario: English stems
- **WHEN** the query is `running` and a page says only `runs`
- **THEN** that page is returned with `match: "lemma"`

#### Scenario: Exact outranks lemma in the same field
- **WHEN** page A's body contains `кошка` and page B's body contains only `кошек`, and the query is `кошка`
- **THEN** A is listed before B, with A reporting `match: "exact"` and B `match: "lemma"`

#### Scenario: Substring matching is kept
- **WHEN** the query is `нейро` and a page contains only `нейросеть`
- **THEN** that page is returned with `match: "substring"`

#### Scenario: й is not и
- **WHEN** the query is `мой` and a page contains only `мои`
- **THEN** the page is not returned by the exact or substring tiers, and is returned only if the two words share a dictionary form

#### Scenario: ё matches е
- **WHEN** the query is `ежик` and a page title is `Ёжик в тумане`
- **THEN** that page is returned with `match: "exact"`

#### Scenario: Exact mode
- **WHEN** the query is `кошка --exact` and one page contains `кошка` while another contains only `кошек`
- **THEN** only the first page is returned

#### Scenario: Search by author
- **WHEN** two source pages have `authors: ["[[Владимир Колдин]]"]` and a third has another author, and the user runs `wiki search --author "Владимир Колдин"`
- **THEN** exactly the two pages by Владимир Колдин are returned

#### Scenario: Declined author name
- **WHEN** the user runs `wiki search --author Колдина`
- **THEN** pages whose authors include `Владимир Колдин` are returned

#### Scenario: Author combined with terms
- **WHEN** the user runs `wiki search инвестиции --author Колдин`
- **THEN** only pages by Колдин that also match `инвестиции` are returned

#### Scenario: Raw files by author
- **WHEN** the user runs `wiki search --author Колдин --raw`
- **THEN** raw files whose frontmatter `authors` include Колдин are returned

### Requirement: Vault status
`wiki status` SHALL report the vault path, page counts per type, total and pending raw source counts, the list of pending raw sources, whether `index.md` is stale, and the most recent log entry heading. It SHALL also report template freshness: the counts of template-managed files that are outdated (a known older version), edited, missing, and obsolete, plus the paths with a pending `<path>.new` merge. The human-readable output SHALL suggest `wiki upgrade` when anything is outdated, missing or obsolete. Computing template freshness SHALL NOT write any file.

#### Scenario: Status after capture
- **WHEN** one URL has been captured but no source page references it
- **THEN** `wiki status --json` reports one pending source with its path and title

#### Scenario: Outdated templates reported
- **WHEN** a vault still has an untouched older `AGENTS.md` and the old `.claude/commands/ingest.md`
- **THEN** `wiki status --json` reports `AGENTS.md` as outdated and `ingest.md` as obsolete, and the text output suggests `wiki upgrade`

#### Scenario: Fresh vault
- **WHEN** `wiki status` runs on a vault just created by the current `wiki init`
- **THEN** it reports no outdated, edited, missing or obsolete templates and no pending merges

### Requirement: Disposable search cache
Search MAY store derived word-form data in `.llmwiki/cache/` inside the vault. The cache SHALL contain its own `.gitignore` that ignores everything in it, so it never appears as a change in git. Deleting the cache at any time SHALL NOT change search results. If the cache cannot be created or written, search SHALL still work, just more slowly. No command other than `wiki search` SHALL depend on the cache.

#### Scenario: Cache stays out of git
- **WHEN** `wiki search` runs in a vault that is a git repository, including one created before this change
- **THEN** `git status` shows no new untracked files from the cache

#### Scenario: Deleting the cache
- **WHEN** the user deletes `.llmwiki/cache/` and repeats a search
- **THEN** the results are identical to the run before deletion

#### Scenario: Unwritable cache
- **WHEN** `.llmwiki/cache/` cannot be written
- **THEN** `wiki search` still returns correct results and exits 0
