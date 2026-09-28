# rp-digest Specification

## Purpose

Turns the weekly news digests of the newspaper «Суть времени» on rossaprimavera.ru into separately dated, attributed wiki items. Each item keeps the quoted outlet's text apart from the newspaper's editorial comment, so both can be found and cited as background.

## Requirements

### Requirement: Parse a digest into items
`wiki source-items-rp <raw>` SHALL read the stored original HTML (`original_file`) of the given raw file and report the digest's issue and its items. It is specific to the digest markup of rossaprimavera.ru.
- Markup:
  - a section is a level-3 heading;
  - an item starts at a dateline paragraph (`block_date`);
  - its text is the following quote paragraphs (`quote`);
  - its comment is the following editorial comment paragraphs (`block_comment`), up to the next dateline or section.
- Bulleted lists:
  - a bulleted list (`ul`) inside an item SHALL be part of that item, with each bullet as one paragraph written `- <text>`;
  - it belongs to the same part (quote or comment) as the paragraph just before it;
  - a list directly after a dateline belongs to the quote;
  - a list before any dateline in a section SHALL be reported as unassigned text, like a stray quote.
- Unknown blocks: any other block with text inside the digest's items SHALL be reported as an `unknown_block` problem with its text, and SHALL NOT be dropped silently. This covers, for example, a paragraph without a digest class, a numbered list, a blockquote or a table. Either this or unassigned text makes the command exit 1.
- Ignored:
  - elements hidden from readers (the `hidden` attribute, inline `display: none` or `visibility: hidden`);
  - advertising containers, embedded widgets and scripts;
  - figures and their captions;
  - blocks without text;
  - everything before the first section heading or dateline, such as the article title and the list of section titles.
- Issue fields:
  - `title` (the article title);
  - `newspaper` and `number` when the page names the issue (e.g. «Суть времени» №682);
  - `published` (the issue date: the raw file's `published`, else the date from the page).
- Item fields:
  - `n` (1-based, in page order);
  - `section`;
  - `dateline` (as written);
  - `place`;
  - `date` (`YYYY-MM-DD`);
  - `outlet` (without surrounding quotation marks);
  - `quote` (paragraphs, verbatim);
  - `comment` (paragraphs, verbatim, or null).
- Text normalisation:
  - non-breaking spaces become spaces and whitespace is collapsed;
  - emphasis is kept as markdown `*…*`;
  - bullets are prefixed with `- `;
  - no other change is made to the text.

The command SHALL NOT modify any file. `--json` SHALL return one document.

#### Scenario: Items with and without comments
- **WHEN** a digest has a section «На фронтах» with two datelines, «ЗАРЕЧЬЕ, 18 сентября — «Вестник»» followed by two quotes and one comment, and «ЛЕСНОЙ, 19 сентября — РИА Север» followed by one quote
- **THEN** item 1 has place `ЗАРЕЧЬЕ`, outlet `Вестник`, two quote paragraphs and one comment paragraph, and item 2 has outlet `РИА Север` and `comment: null`

#### Scenario: Hidden and service markup ignored
- **WHEN** an item's text is interrupted by an advertising container, an embedded video widget and a paragraph with `style="display: none"`
- **THEN** none of their text appears in the item, and the quote paragraphs on both sides of them belong to the same item

#### Scenario: Emphasis kept
- **WHEN** a quote paragraph is `<p class="quote"><em>Текст</em> и далее</p>`
- **THEN** the item's quote paragraph is `*Текст* и далее`

#### Scenario: List continues the quote
- **WHEN** an item's quote paragraph ending «Детали:» is followed by three `ul` blocks with one bullet each, and then by another quote paragraph
- **THEN** the item's quote has five paragraphs in page order: the first quote, `- <bullet 1>`, `- <bullet 2>`, `- <bullet 3>` and the last quote

#### Scenario: List continues the comment
- **WHEN** an editorial comment paragraph is followed by a `ul` with two bullets
- **THEN** both bullets are added to the item's comment, not its quote

#### Scenario: List right after a dateline
- **WHEN** a dateline is directly followed by a `ul`
- **THEN** its bullets are the start of the item's quote

#### Scenario: Unknown block reported
- **WHEN** an item contains a paragraph without a digest class, with the text «Непонятный абзац»
- **THEN** the command reports an `unknown_block` problem with that text and exits 1, and the item's other paragraphs are reported normally

#### Scenario: Header and cover ignored
- **WHEN** the page has the article title, a list of section titles and a cover figure with a credit before the first section heading
- **THEN** none of them is reported as a problem or appears in any item

### Requirement: Item dates carry the issue's year
A dateline gives a day and a Russian month name without a year. The item's `date` SHALL take the year of the issue date. If that would put the item after the issue date, the date SHALL move to the previous year. If the issue date is unknown, the command SHALL fail with error code `no_issue_date` (exit 2). A dateline that does not parse SHALL still produce an item, with `date: null` and its `dateline` as written, and the command SHALL exit 1 and report it as a problem.

#### Scenario: Same year
- **WHEN** the issue is dated 2026-09-26 and a dateline reads «18 сентября»
- **THEN** the item's date is `2026-09-18`

#### Scenario: Year boundary
- **WHEN** the issue is dated 2027-01-09 and a dateline reads «29 декабря»
- **THEN** the item's date is `2026-12-29`

#### Scenario: Unparseable dateline
- **WHEN** a dateline reads «ЗАРЕЧЬЕ — «Вестник»» with no date
- **THEN** that item has `date: null`, the other items are reported normally, and the command exits 1

### Requirement: Refuse unknown formats
`wiki source-items-rp` SHALL fail with exit code 2 in these cases, and SHALL NOT guess:
- error code `not_rp_digest` when the stored original contains no dateline paragraphs (for example an ordinary rossaprimavera.ru article, or a changed page layout);
- error code `no_original` when the raw file has no stored original.

#### Scenario: Ordinary article
- **WHEN** the raw file was captured from a rossaprimavera.ru article without datelines
- **THEN** the command exits 2 with error code `not_rp_digest`

#### Scenario: Text file source
- **WHEN** the raw file was captured from a `.txt` file
- **THEN** the command exits 2 with error code `no_original`

### Requirement: Digest page model
A digest SHALL be represented in the wiki as one hub source page for the issue and one source page per item. All of them SHALL have `raw:` pointing at the same raw file.
- The hub page SHALL have the issue's `published` and link every item page.
- Each item page SHALL have:
  - `item: <n>`;
  - `published: <item date>`;
  - `outlet: <outlet>`;
  - `via: "[[<hub page>]]"`;
  - `commentary: true` exactly when the item has a comment.
- Item page bodies SHALL contain the quote verbatim under a heading naming the outlet and date. The comment SHALL be verbatim under a separate heading attributing it to the newspaper and the issue date.

`item` SHALL be a positive integer, `outlet` a string, `via` a string and `commentary` a boolean. These fields are optional on all other source pages.

#### Scenario: Item page with a comment
- **WHEN** item 7, dated 2026-09-18 from outlet `Вестник` with a comment, is ingested from issue hub `Суть времени №682`
- **THEN** its source page has `item: 7`, `published: 2026-09-18`, `outlet: Вестник`, `via: "[[Суть времени №682]]"`, `commentary: true`, and separate headings for the quote and the editorial comment

### Requirement: Schema and ingest workflow cover digests
The `AGENTS.md` schema, in every language, SHALL describe the digest page model and SHALL state that an editorial comment is the newspaper's opinion. It SHALL be attributed to the newspaper and never presented as a statement of the quoted outlet or as a fact. The ingest workflow SHALL use this branch only for raw files whose frontmatter has `format: rp-digest`:
- run `wiki source-items-rp <raw> --json` instead of reading the flattened body;
- create the hub page and one item page per item with the fields above;
- link entities and concepts to item pages with dated, attributed claims;
- stop and report when the command exits 2;
- ask the human about items with `date: null`.

#### Scenario: Workflow branch
- **WHEN** the rendered ingest workflow is inspected
- **THEN** it tells the agent to run `wiki source-items-rp` for raw files with `format: rp-digest`, to create one source page per item plus a hub page, and to keep comments verbatim and attributed to the newspaper

#### Scenario: Schema in another language
- **WHEN** a vault is initialised with `--language ru`
- **THEN** its `AGENTS.md` contains the digest page model and the attribution rule for editorial comments
