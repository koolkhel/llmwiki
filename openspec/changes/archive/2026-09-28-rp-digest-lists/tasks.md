## 1. Fixtures

- [x] 1.1 Add synthetic bodies to `tests/rpfixture.py`, all with invented content:
  - a quote ending «Детали:» followed by three one-bullet `ul`s and another quote;
  - a comment followed by a two-bullet `ul`;
  - a `ul` right after a dateline;
  - a `ul` before any dateline in a section;
  - an item with a class-less `<p>`, and one with a `<table>`.

  Also add a page header like the real one to `digest_html`: `div.pre_title` with the section titles, and a `figure` cover with a credit before the first `h3`. Verify that the existing fixture tests still load.

## 2. Parser

- [x] 2.1 Rewrite the walk in `rpdigest.parse_html` over the container's direct children (D1–D4):
  - the header zone;
  - `ul` bullets as `- …` of the previous kind;
  - lists before any dateline reported as unassigned;
  - `figure` and textless blocks ignored;
  - `unknown_block` problems.

  Verify with tests for every scenario in `specs/rp-digest`: the three existing ones, the two list-continuation scenarios, the list right after a dateline, the unknown block, and the header and cover. Also check the list-before-dateline and table cases, and that the whole existing `tests/test_rpdigest.py` still passes.

## 3. Verification

- [x] 3.1 Run the full test suite and confirm it passes.
- [x] 3.2 Real-page check, without writing to any vault:
  - on https://rossaprimavera.ru/article/f0a2c804 (№681): 24 items, no problems, item 2's quote has its 3 bullets and item 6's has its 6, in page order, and the comment counts stay at 3 items and 4 paragraphs;
  - on https://rossaprimavera.ru/article/4c87c842 (№682): the output is identical to before the change (26 items, no problems).

  Record the results in design.md, then commit, push, and confirm CI passes.
