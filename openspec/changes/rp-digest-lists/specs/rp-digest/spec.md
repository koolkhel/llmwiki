## MODIFIED Requirements

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
