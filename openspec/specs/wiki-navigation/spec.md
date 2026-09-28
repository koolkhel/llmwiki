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
`wiki search <query>` SHALL return pages matching all query terms, searching title, aliases, summary, tags and body. `aliases` (a frontmatter list, entries may be wikilinks) SHALL be treated as part of the title field for matching and ranking. A term matches a page when it matches in at least one of three tiers:
1. **exact**: the term equals a word of the page after folding;
2. **lemma**: the term and a word of the page share a dictionary form (Russian) or stem (English), taking every possible dictionary form of an ambiguous word into account;
3. **substring**: the folded term occurs anywhere in the folded text.

Folding SHALL be case-insensitive and SHALL ignore Latin diacritics. `ё` SHALL match `е`, and Cyrillic `й` SHALL remain distinct from `и`. Combining marks of non-Latin scripts (for example Devanagari vowel signs, virama and nukta) SHALL be kept by folding and SHALL NOT split words. A run of CJK ideographs SHALL, in addition to being one word, be indexed as its overlapping two-character sequences, so that a query of two or more ideographs contained in the run matches at the exact tier.

Results SHALL be ranked so that title matches outrank summary/tag matches, which outrank body-only matches. Within the same field, exact matches SHALL outrank lemma matches, which SHALL outrank substring matches.

Each result SHALL include `path`, `title`, `type`, `summary`, `link`, `match`, and a short body snippet around the first matching word. `match` is the weakest tier any query term needed (`exact`, `lemma` or `substring`).

`--type` SHALL restrict results to one page type, `--limit` SHALL cap the count (default 20), and `--raw` SHALL search raw sources instead of wiki pages, with the same matching. `--exact` SHALL disable the lemma and substring tiers.

`--author <name>` SHALL restrict results to pages (with `--raw`: raw files) whose frontmatter `authors` contains a name matching every word of `<name>`, using the exact and lemma tiers (only exact with `--exact`). Wikilink brackets and aliases in `authors` entries are ignored for matching. An author entry that links to a page SHALL also match through that page's `aliases`. When `--author` is given, query terms are optional: without them, all pages by that author are returned, sorted by title.

`--since <date>` and `--until <date>` SHALL restrict results to pages (with `--raw`: raw files) whose frontmatter `published` falls within the range, inclusive, where `<date>` is `YYYY`, `YYYY-MM` or `YYYY-MM-DD` (a partial date covers its whole year or month). Pages without a parseable `published` SHALL be excluded when either filter is given. `--sort oldest|newest` SHALL order results by `published` (undated last), replacing the relevance order. When `--since`, `--until` or `--sort` is given, query terms SHALL be optional, as with `--author`. An invalid date SHALL be a usage error. Each result SHALL include `published` when the page has one.

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

#### Scenario: Query in another language finds the concept via aliases
- **WHEN** the English page `Large language model` has `aliases: [Большая языковая модель, 大语言模型, बड़ा भाषा मॉडल]`, and the user searches `языковая модель`, `大语言模型` or `भाषा मॉडल`
- **THEN** that page is returned, ranked as a title match

#### Scenario: Hindi words stay whole
- **WHEN** a page body contains `प्रशिक्षित` and another contains `परशिकषित`
- **THEN** searching `प्रशिक्षित` returns only the first page at the exact tier

#### Scenario: Chinese two-character matching
- **WHEN** a page body contains `大语言模型的训练需要大量数据`, and the user searches `模型` or `训练`
- **THEN** the page is returned with `match: "exact"`

#### Scenario: Author found via person-page alias
- **WHEN** a source page has `authors: ["[[Fei-Fei Li]]"]`, and `wiki/entities/Fei-Fei Li.md` has `aliases: [李飞飞]`, and the user runs `wiki search --author 李飞飞`
- **THEN** that source page is returned

#### Scenario: Filter by period
- **WHEN** source pages are published 2026-01-15, 2026-04-09 and 2026-08-02, and the user runs `wiki search --since 2026-04 --until 2026-06`
- **THEN** only the 2026-04-09 page is returned

#### Scenario: Chronological order
- **WHEN** the user runs `wiki search ИИ --sort oldest`
- **THEN** matching pages are listed from the earliest `published` to the latest, with undated pages last

#### Scenario: Invalid date
- **WHEN** the user runs `wiki search --since 2026-13`
- **THEN** the command exits with code 2

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

### Requirement: Timeline
`wiki timeline <page>` SHALL list, in publication order, the source pages connected to a wiki page given by title or vault path: the source pages listed in its `sources` frontmatter, the source pages that link to it, and, for a page tagged `person`, the source pages whose `authors` resolve to it. Duplicates are merged. `wiki timeline --author <name>` SHALL instead list the source pages whose authors match `<name>` as in search. Each entry SHALL give `published` (as recorded on the source page, or the raw file's more precise value when available), the source page's `title`, `link`, `path`, `authors` and `summary`. Entries are sorted by the most precise date available, with undated entries last and marked `undated`. `--since`/`--until` SHALL filter as in search, and `--json` SHALL return one document. An unknown page SHALL be an error (exit code 2). The command SHALL NOT modify any file.

#### Scenario: Concept timeline
- **WHEN** `Large language model` is linked from source pages published 2026-08-02 and 2026-01-15, lists a third, undated source page in its `sources`, and the user runs `wiki timeline "Large language model"`
- **THEN** the output lists the 2026-01-15 source, then the 2026-08-02 source, then the undated one

#### Scenario: Person timeline
- **WHEN** the person page `Анатолий Янченко` exists and two source pages have `authors: ["[[Анатолий Янченко]]"]`
- **THEN** `wiki timeline "Анатолий Янченко"` lists both, in publication order

#### Scenario: Timeline by author name
- **WHEN** the user runs `wiki timeline --author Янченко --since 2026`
- **THEN** only that author's sources published in 2026 or later are listed, in order

#### Scenario: Same-day ordering uses time
- **WHEN** two sources are both published on 2026-04-09, with raw times 06:25+03:00 and 18:00+03:00
- **THEN** the 06:25 source comes first

### Requirement: Commentary filter and outlet in results
`wiki search --commentary` SHALL restrict results to pages whose frontmatter has `commentary: true`. With `--raw` it SHALL be a usage error. It SHALL combine with query terms and with every other filter. When it is given, query terms SHALL be optional, as with `--author`. Search results and timeline entries SHALL include `outlet` when the source page has one.

#### Scenario: Only commented items
- **WHEN** two item pages mention «градирня», and only one has `commentary: true`
- **THEN** `wiki search градирня --commentary` returns only that one

#### Scenario: Commented items in a period
- **WHEN** the user runs `wiki search --commentary --since 2026-09 --sort newest`
- **THEN** all commented item pages published in September 2026 or later are returned, newest first

#### Scenario: Outlet shown
- **WHEN** an item page has `outlet: Вестник` and appears in a search result or a timeline
- **THEN** that result or entry includes `outlet: "Вестник"`

#### Scenario: Not for raw search
- **WHEN** the user runs `wiki search градирня --raw --commentary`
- **THEN** the command exits 2 with a usage error
