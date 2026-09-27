## ADDED Requirements

### Requirement: Record authors
Captures of URLs, saved web pages and `.md` files SHALL record the source's authors in raw frontmatter as `authors`: an ordered list of names, each whitespace-normalised, with duplicates removed and the first occurrence kept. Authors SHALL be taken from the first of these that yields at least one name:
1. JSON-LD on the page: the `author` of the page's main article object (a Person/Organization `name`, a list of them, or a plain string);
2. the page author found by the text extractor's metadata;
3. the authors found by the news-metadata extractor;
4. for `.md` files only, an `author` or `authors` key in the file's original frontmatter.

Authors from elements that describe other content on the page (related-article widgets, sidebars) SHALL NOT be recorded. When no authors are found, the `authors` key SHALL be omitted rather than written empty. `.txt` captures record no authors.

#### Scenario: Author in JSON-LD and byline
- **WHEN** a page has `"author":[{"@type":"Person","name":"Владимир Колдин"}]` in JSON-LD and a sidebar widget listing "Максим Карев, Владимир Колдин" for another article
- **THEN** the raw file records `authors: [Владимир Колдин]`, without Максим Карев

#### Scenario: Several authors keep their order
- **WHEN** the article's JSON-LD lists authors "Anna A" then "Boris B"
- **THEN** `authors` is `[Anna A, Boris B]`

#### Scenario: Metadata fallback
- **WHEN** a page has no JSON-LD author but has `<meta name="author" content="Jane Doe">`
- **THEN** `authors` is `[Jane Doe]`

#### Scenario: Web Clipper markdown
- **WHEN** a `.md` file with frontmatter `author: "[[Jane Doe]]"` or `author: [Jane Doe, John Roe]` is captured
- **THEN** `authors` holds the plain names (`[Jane Doe]` or `[Jane Doe, John Roe]`), without wikilink brackets

#### Scenario: No author anywhere
- **WHEN** no author signal exists
- **THEN** the raw file has no `authors` key

### Requirement: Re-derive source metadata
`wiki source-meta <raw file>` SHALL re-derive capture metadata for an existing raw file from its stored original (`original_file` under `raw/.orig/`) using the current extraction rules, and print at least `path`, `title`, `authors`, `published`, `language` and `canonical_url`, along with the values recorded in the raw file. It SHALL NOT modify any file. For raw files without a stored original, it SHALL report the recorded values and `derivable: false`. `wiki source-meta --all` SHALL list every raw file whose re-derived or recorded authors are non-empty while its source page (if any) has no `authors`, giving the raw path, the source page path (or null if not ingested) and the authors.

#### Scenario: Backfill an older capture
- **WHEN** a raw file captured before authors were recorded has an `.orig` HTML with a JSON-LD author, and its source page has no `authors`
- **THEN** `wiki source-meta --all --json` lists that raw file with the source page path and the derived authors, and no file changes

#### Scenario: Read-only
- **WHEN** `wiki source-meta` runs on any raw file
- **THEN** every file in the vault is byte-identical afterwards

#### Scenario: No stored original
- **WHEN** the raw file came from a `.txt` capture
- **THEN** the output shows the recorded values and `derivable: false`
