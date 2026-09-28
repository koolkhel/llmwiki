## Context

See proposal.md. Today `parse_html` walks `root.find_all(["h3", "p"])` under the lowest common ancestor of all datelines, and acts only on `p.block_date`, `p.quote` and `p.block_comment`. Everything else is invisible to it.

In both real issues checked (№681 and №682), the item container's **direct children** are a flat sequence:
- before the items: `div.pre_title` (the section titles), `h1`, `div.back-article-…` (empty) and `figure.art_img` (the cover with its credit);
- the items: `h3`, `p.block_date`, `p.quote`, `p.block_comment`, class-less `ul` (one `li` each in №681), `div.ad_container`, `script` and `div.widget.embed`;
- after the items: `div.comment_position` (empty).

## Goals / Non-Goals

**Goals:**
- Keep list text, in its place and in the right voice.
- Make any unrecognised content loud.

**Non-Goals:**
- Numbered lists, tables or blockquotes as content. They are reported instead, and supported later only if a real issue needs them.
- Merging one-bullet lists into one paragraph.
- Nested lists (none seen).

## Decisions

### D1. Walk the container's direct children, not all descendants
Iterate `root.children` (tags only) after the existing removal of hidden and service elements. Each child is classified once:
- `h3` → section;
- `p.block_date` → item;
- `p.quote` / `p.block_comment` → text of that kind;
- `ul` → its `li`s, each as `- <text>`, of the kind of the previous text block (`quote` if none since the dateline);
- `figure` or no text → ignored;
- anything else with text → `unknown_block`.

Before the first `h3` or dateline, every child is ignored (the header zone).

**Why direct children:** both pages are flat, and descending into `div`s would re-read nested text and double-count it. If a future layout nests items inside wrappers, the datelines' common ancestor changes, and whatever is unrecognised turns into `unknown_block`. So a layout change is still loud rather than silent.

**Alternative rejected:** keep `find_all` and add `li`. That would also silently pick up `li`s from nested widgets, and it would still miss plain `p`s and tables.

### D2. The "previous kind" is tracked per item
`last_kind` resets to `quote` at every dateline and to none at every `h3`. A `ul` with `last_kind` none (before any dateline in the section) goes to `unassigned` with `kind: "quote"` and a problem `unassigned_text`, exactly like a stray quote paragraph.

### D3. Bullet text
Each bullet's text goes through `_text` (so emphasis is kept) and is prefixed with `- `. An empty `li` is skipped. Bullets are separate entries in the `quote`/`comment` list, so a page can render them as a markdown list inside the blockquote (`> - …`). The item page layout in `AGENTS.md` still holds, and no template changes.

### D4. `unknown_block` problem shape
It is `{"code": "unknown_block", "item": <n or null>, "section": …, "tag": "p", "text": <normalised text, first 200 chars>, "message": …}`. Every problem makes the command exit 1, and the ingest workflow already stops and reports problems to the human. The item keeps its other text.

## Risks / Trade-offs

- **A real issue could contain a class-less paragraph that is legitimately part of the quote.** → It becomes `unknown_block` and the human decides. If it recurs, a later change adds the rule, the same way lists were added here.
- **Numbered lists appear in a future issue.** → They are reported, not lost. This is a one-line extension of D1 once seen.
- **The direct-children walk fails on a nested layout.** → Unknown blocks and the `not_rp_digest` check keep the failure loud.

## Verification (2026-09-28)

- **№681 (https://rossaprimavera.ru/article/f0a2c804):** 24 items, no problems, nothing unassigned.
  - Item 2's quote is 6 entries, with its 3 bullets between «…может затронуть:» and the closing paragraph.
  - Item 6's quote is 7 entries: «…Детали:»-style opening plus the 6 bullets, in page order.
  - Comments are unchanged: 3 items, 4 paragraphs.
- **№682 (https://rossaprimavera.ru/article/4c87c842):** the JSON output is identical to the previous parser's (26 items, no problems).
