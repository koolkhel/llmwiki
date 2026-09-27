## MODIFIED Requirements

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

## ADDED Requirements

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
