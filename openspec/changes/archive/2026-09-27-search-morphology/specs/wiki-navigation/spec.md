## MODIFIED Requirements

### Requirement: Search pages
`wiki search <query>` SHALL return pages matching all query terms, searching title, summary, tags and body. A term matches a page when it matches in at least one of three tiers:
1. **exact**: the term equals a word of the page after folding;
2. **lemma**: the term and a word of the page share a dictionary form (Russian) or stem (English), taking every possible dictionary form of an ambiguous word into account;
3. **substring**: the folded term occurs anywhere in the folded text.

Folding SHALL be case-insensitive and SHALL ignore Latin diacritics. `ё` SHALL match `е`, and Cyrillic `й` SHALL remain distinct from `и`.

Results SHALL be ranked so that title matches outrank summary/tag matches, which outrank body-only matches. Within the same field, exact matches SHALL outrank lemma matches, which SHALL outrank substring matches.

Each result SHALL include `path`, `title`, `type`, `summary`, `link`, `match`, and a short body snippet around the first matching word. `match` is the weakest tier any query term needed (`exact`, `lemma` or `substring`).

`--type` SHALL restrict results to one page type, `--limit` SHALL cap the count (default 20), and `--raw` SHALL search raw sources instead of wiki pages, with the same matching. `--exact` SHALL disable the lemma and substring tiers.

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

## ADDED Requirements

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
