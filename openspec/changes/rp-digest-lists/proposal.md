## Why

`wiki source-items-rp` reads only dateline, quote and comment paragraphs, so anything else inside a digest is dropped without a warning. Issue №681 (https://rossaprimavera.ru/article/f0a2c804) shows the gap. Its news text continues in bulleted lists, plain `<ul>` blocks with one bullet each. Item 6 would keep only the sentence ending «Детали:» and lose all six details. The command still exits 0, and nothing downstream notices, which breaks the rule that the parser never guesses.

## What Changes

- Bulleted lists (`<ul>`) inside an item become part of the item. Each bullet is one `- …` line, added to the same part as the paragraph before it (quote or comment). A list directly after a dateline counts as quote. A list before any dateline in a section is reported as unassigned text, like a stray quote.
- Any other block with text inside the digest's items is reported as an `unknown_block` problem with its text (exit 1), never silently dropped. Examples are a plain paragraph, a numbered list, a blockquote or a table.
- Still ignored:
  - the cover figure and its credit;
  - the list of section titles above the first section;
  - blocks without text, such as the empty comments anchor;
  - the service markup that was already ignored.
- No change to the JSON shape, the page model, capture, lint, search or templates. Nothing is ingested in digest form yet, so there is nothing to migrate.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities
- `rp-digest`: the "Parse a digest into items" requirement adds bulleted lists to items and reports unknown blocks.

## Impact

- Code: `src/llmwiki/rpdigest.py` (walk over the item container's blocks).
- Tests: synthetic fixtures in `tests/rpfixture.py` with the list shapes of №681 (a list after a quote, after a comment, right after a dateline, before any dateline) and unknown blocks, plus `tests/test_rpdigest.py`.
- No template, hash-registry, dependency or README change.
