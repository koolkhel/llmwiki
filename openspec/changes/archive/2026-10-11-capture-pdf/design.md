## Context

`add-source` has three capture paths (URL, saved HTML and text file), all in `sources.py`. Each writes an immutable raw `.md` file and, for HTML, an unmodified original under `raw/.orig/` named after the raw file's stem. Dispatch is by argument shape and file suffix (`capture()`); unsupported suffixes raise `unsupported_file`. `derive_meta()` assumes every stored original is HTML.

The spike (scratchpad, not committed) ran pdfminer.six 20260107 on a 67-page Word-generated preprint:
- **Speed:** full extraction took 2.4 s.
- **Layout signals:**
  - body text: 12 pt;
  - headings: a bold face;
  - captions and footnotes: about 10 pt;
  - footnote markers: superscripts of 6.5–7.9 pt;
  - page number: a short centred line below y≈50;
  - references: a hanging indent (number at x=72, continuation lines at x=108).
- **Approach:**
  - Reading pdfminer's own text boxes scrambled right-aligned text and split reference numbers from their entries, and it put two footnotes in one box.
  - Rebuilding visual lines from individual characters fixed all of these.

## Goals / Non-Goals

**Goals:**
- Extraction is deterministic: the same PDF and the same extractor version give the same body bytes, so `sha256` and duplicate detection stay meaningful.
- Thresholds are relative to each document (body size measured per document), not absolute point sizes, so that LaTeX papers (10–11 pt body) and Word papers (12 pt) both work.
- Classification failures degrade to plain paragraphs, never to lost text. Every character of body, caption, footnote and reference text ends up in the output exactly once.

**Non-Goals:**
- Two-column layouts, tables as tables, mathematics beyond the text characters pdfminer reports, figure images, and OCR.
- Page anchors in the body (e.g. `<!-- p. 12 -->`). They can be added later as a new extractor version.
- Language detection for PDFs (`language` is omitted).
- Backfilling or re-extracting existing captures.

## Decisions

### 1. pdfminer.six, characters rebuilt into lines

`extract_pages()` with default `LAParams`; walk every `LTChar` and keep its text, font name, size, `x0`, `x1`, `y0` and `y1`. Group the characters on each page into lines by baseline, sort each line by `x0`, and insert a space where the gap exceeds a fraction of the font size. The spike used 2 pt baseline buckets and a gap of 0.25 × size. Superscript characters (size < 0.8 × the line's dominant size, raised above its baseline) are attached to the line they belong to, as markers, rather than forming their own line.

- *Alternatives:*
  - `pdftotext`/poppler: an external binary, with no font information;
  - PyMuPDF: AGPL;
  - pypdf: weak layout;
  - pdfminer's own `LTTextBox` output: the scrambling problems described above.
- pdfminer is MIT, pure Python and already proven on the target paper.

### 2. Line classification, relative to the document

First pass over all lines: the **body size and font** are the mode of character sizes weighted by character count. Then each line is classified, in this order:

| Class | Signal |
|---|---|
| `page_number` | a line of digits only (or "Page n" / "n of m") in the bottom or top 8 % of the page |
| `running` | same text (digits masked) at the same position (±2 pt) on at least half the pages |
| `title` | page 1, upper half, largest size in the document |
| `heading` | bold (font name contains Bold/Black/Semibold or the font flags say so), or size ≥ 1.15 × body, and short (< 120 characters, at most two lines) |
| `caption` | size < body and the text starts with `Figure|Fig.|Table` + number + `:` or `.`; continuation lines follow at the same size |
| `footnote` | size < body, in the bottom zone of the page below the last body line, starts with a number that matches a superscript marker seen on that page or earlier |
| `reference` | after a heading matching `References|Bibliography|Literature( Cited)?` (case-insensitive): a numbered or bracketed entry start (`64.`, `[64]`) at the left margin, continuation at the hanging indent |
| `toc` | after a `Contents` heading: a line ending with a page number (rendered as one list, dot leaders removed) |
| `body` | everything else |

Characters that are not upright (rotated text such as arXiv's vertical margin stamp) are dropped before lines are built. In the references, entries are split by the hanging indent when there is one (a line at the left edge starts an entry; when most left-edge lines are numbered, the number is required as well, because some numbered lists wrap continuation lines to the left edge), else by the number pattern or a vertical gap. Body paragraphs starting with `>`, `#` or `|` (e.g. a displayed inequality) are backslash-escaped.

### 3. Paragraph assembly

Consecutive lines of the same class are joined into one block. A new paragraph starts when:
- the vertical gap is greater than 1.5 × the line's leading;
- or the first line is indented relative to the block's left margin;
- or the previous line ended well short of the right margin and with sentence punctuation.

A block that ends at the bottom of a page continues on the next page's first body line when it did not end with sentence punctuation, or when the next page's first body line starts lowercase and isn't indented. Consecutive short lines (under ¾ of the text width) that share a left or right edge and don't end a sentence are verse, epigraphs or address blocks: they stay one block joined with line breaks. A word hyphenated at a line end (`hyphen-\nation`) is rejoined only when both parts are lowercase letters.

### 4. Markdown rendering

- `# <title>`
- `## <heading>`
- paragraphs separated by blank lines
- `> Figure 3: …`
- footnote markers as `[^n]`, with `[^n]: text` definitions collected and appended after the body in order of first appearance
- references as one line each, `64. Heylighen …`

Literal `[^` already in the text is left alone, since it can't be confused with a marker in practice. Whitespace (tabs, non-breaking spaces and runs of spaces) is normalised to one space, and NFC is applied.

### 5. Refusals

- **`no_text_layer`:** fewer than 50 non-space characters in total, or on average fewer than 20 per page.
- **`multi_column`:** for body lines, cluster `x0` and `x1`. If most body lines on most pages either end before the page's horizontal midpoint or start after it (two separate x-ranges whose union spans the text width), refuse.
- **`pdf_encrypted`:** pdfminer's `PDFPasswordIncorrect` / `PDFEncryptionError`.
- **`pdf_unreadable`:** `PDFSyntaxError` or any other parser failure.

### 6. Metadata

- **Title:** see the spec. The PDF metadata title is ignored when it equals the filename stem or matches `^(untitled|microsoft word|paper v?\d+|document\d*)`, and it is only a fallback anyway.
- **Authors:** see the spec. Superscript characters and trailing digits, `*`, `†` and `‡` are stripped. Splitting is on `,`, `;`, ` and ` and `&`.
- **DOI:** `\b10\.\d{4,9}/[^\s"<>]+` on page 1, with trailing punctuation stripped.
- **`extractor`:** `pdfminer.six <version>`. `pages` is the page count.

### 7. Storage and duplicates

The PDF is copied with `open("xb")` to `raw/.orig/<raw stem>.pdf`, the same naming as HTML originals. `original_sha256` (sha256 of the file bytes) is checked before extraction work is written. Since it is checked against all raw files, a re-add short-circuits even if a newer extractor would produce a different body. The text `sha256` check also still applies.

### 8. `.gitignore` and upgrade

`templates/vault/dot-gitignore` gains:

```
# Stored PDF originals (large; the extracted text in raw/ is committed)
raw/.orig/*.pdf
```

The previous `.gitignore` hash is already in `known_hashes.json`, so `wiki upgrade` replaces untouched copies, and edited copies get a `.gitignore.new`. The same applies to `AGENTS.md` (every language rendering) and the ingest workflow files.

### 9. Code layout

- **New module `src/llmwiki/pdf.py`:** `extract(path) -> PdfDoc` (title, authors, doi, pages, body, extractor), raising `WikiError`. It is read-only and has no vault knowledge.
- **`sources.py`:** `capture_pdf()`; `capture()` dispatches on the `.pdf` suffix; `_source_file()` accepts `.pdf`; `find_duplicate()` gains an `original_sha256` argument; `derive_meta()` branches on `format: pdf` / a `.pdf` original.
- **`lint.py`:** `original_not_local`.

### 10. Synthetic test PDFs

`tests/pdffixture.py` writes minimal PDF 1.4 files by hand: the standard Type 1 fonts Times-Roman, Times-Bold and Helvetica, `BT /F1 12 Tf x y Td (text) Tj ET` objects, and a correct xref. That lets tests place text at exact sizes and positions with no new dependency. All text is invented. The fixtures cover:
- title, authors and abstract;
- bold headings;
- a paragraph across a page break, with a page number;
- a caption;
- a superscript marker and its footnote;
- a reference list with a hanging indent;
- a two-column page;
- an image-only page (no text operators);
- a file that isn't a PDF.

Encryption is tested by making pdfminer's opener raise (monkeypatch).

## Risks / Trade-offs

- **[Heuristics tuned on one paper]** → Thresholds are relative, and every fallback is "plain paragraph". Before archiving, the change is checked on the Levin paper and on the second single-column paper the human has. The results are compared by eye in the scratchpad and never committed.
- **[Ligatures, odd encodings]** (`ﬁ`, fonts without ToUnicode give `(cid:12)`) → NFKC is applied to ligature code points only (U+FB00–FB06). Text with `(cid:` sequences is kept as is, and a warning in the command output names how many occurred.
- **[Large PDFs are slow]** (2.4 s for 67 pages; a 500-page book would take about 20 s) → Acceptable for a one-off capture. No progress output.
- **[Git-ignored originals can be lost]** → `original_sha256` and `original_size` let the human verify a restored copy. `lint` shows `original_not_local` so the gap is visible. The extracted text, which the wiki actually cites, is always committed.
- **[Extractor upgrades change output]** → Existing raw files are immutable. `extractor` records the version. The duplicate check on `original_sha256` prevents accidental second captures.
- **[`cryptography` dependency weight]** → Pulled in by pdfminer.six for encrypted PDFs. Ready-built packages exist for all target platforms.

## Migration Plan

No data migration is needed. After upgrading the tool, `wiki upgrade` in each vault adds the `.gitignore` rule and the schema text. Rolling back the tool leaves PDF raw files readable as ordinary raw files, and `lint` stays clean apart from the info finding, which older versions don't have.
