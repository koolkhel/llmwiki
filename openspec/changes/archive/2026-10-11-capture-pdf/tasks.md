## 1. Setup

- [x] 1.1 Add `pdfminer.six>=20260107` to `pyproject.toml` dependencies, install it into `.venv`, and check that `python -c "import pdfminer; print(pdfminer.__version__)"` prints 20260107 or later and the existing test suite still passes.
- [x] 1.2 Make sure no PDF can be committed by accident: add `*.pdf` to the repository `.gitignore` (the Levin paper sits untracked in the repo root), and check that `git status --porcelain` no longer lists it.
- [x] 1.3 Write `tests/pdffixture.py`, a minimal hand-written PDF 1.4 writer with Times-Roman, Times-Bold and Helvetica, text at explicit positions and sizes, several pages and a correct xref, all with invented text. Check that a smoke test opens a generated two-page file with pdfminer and reads back its text and font sizes.

## 2. Extraction (`src/llmwiki/pdf.py`)

- [x] 2.1 Character walk and line rebuild: group by baseline, sort by x, insert spaces from gaps, attach superscripts to their line as markers, and normalise whitespace, ligatures (U+FB00–FB06) and NFC. Check with a unit test on a fixture with a right-aligned line and a superscript that the lines come out in reading order with the marker attached.
- [x] 2.2 Document statistics and line classification: body size and font as a weighted mode, then `page_number`, `running`, `title`, `heading`, `caption`, `footnote`, `reference` and `body`, per design §2. Check with unit tests that each class is recognised on a fixture, and that a document with a 10 pt body classifies the same way as one with a 12 pt body.
- [x] 2.3 Paragraph assembly and markdown rendering: paragraph breaks, joining across pages, rejoined hyphenation, `# title`, `## headings`, `> Figure n:` captions, `[^n]` markers with `[^n]:` definitions at the end, and one line per reference. Check that the tests for the spec scenarios "Structure preserved" and "Paragraph across a page break" pass, and that no input text is lost: every non-space character of the fixture appears in the output, apart from page numbers and running headers.
- [x] 2.4 Metadata: the title (page-1 largest text, then a metadata title that isn't a placeholder, then the filename stem), authors (metadata, then the page-1 name line, else none), DOI, `pages` and `extractor`. Check that the tests for "Wrong metadata title", "Authors from page 1", "No recognisable authors", "DOI on page 1" and "Creation date is not a publication date" pass.
- [x] 2.5 Refusals: `no_text_layer`, `multi_column`, `pdf_encrypted` (a monkeypatched opener) and `pdf_unreadable`, each a `WikiError`. Check that the tests for the scenarios "Scanned PDF", "Two-column paper", "Password-protected PDF" and "Not a PDF" pass, and that a single-column page with a centred title or a wide figure caption is *not* refused.

## 3. Capture integration (`sources.py`, `cli.py`)

- [x] 3.1 `capture_pdf()`:
  - accept `.pdf` in `_source_file()`;
  - dispatch from `capture()`, with `--url` rejected as `invalid_option`;
  - write the raw file with the spec's frontmatter;
  - copy the PDF with `open("xb")` to `raw/.orig/<stem>.pdf`;
  - write nothing on any error.

  Check that the end-to-end test for "Single-column paper" passes through `wiki add-source --json`, the source file's bytes and mtime are unchanged, and no file under `raw/` exists after each refusal.
- [x] 3.2 Duplicate detection on `original_sha256`, checked before anything is written. Check that the "Same PDF again" test passes (the same bytes from a different path give `duplicate_of`, with no new `.md` or `.pdf`) and that the existing duplicate tests still pass.
- [x] 3.3 `derive_meta()` and `source-meta` for PDF originals: PDF rules when the original is a `.pdf`, `derivable: false` when it is absent. Check that the tests for "PDF capture" and "PDF not on this machine" pass, and that the read-only test covers a vault with a PDF capture.
- [x] 3.4 Update the `add-source` help text in `cli.py` to list `.pdf`. Check that `wiki add-source --help` shows it.

## 4. Lint

- [x] 4.1 `original_not_local` (info) for `format: pdf` raw files whose `original_file` is missing. Check that the "Cloned vault without its PDFs" test passes (exit 0) and that a vault whose PDF is present reports nothing.

## 5. Templates and upgrade

- [x] 5.1 Add `raw/.orig/*.pdf` with a comment to `templates/vault/dot-gitignore`. Check with a test that in a git-initialised vault after a PDF and an HTML capture, `git check-ignore` matches the PDF and not the HTML.
- [x] 5.2 Update `templates/vault/AGENTS.md`:
  - the Layers row: "original HTML or PDF in `raw/.orig/`; PDFs not committed";
  - the add-source paragraph: `.pdf`, single-column with a text layer only;
  - the Chronology rule: a PDF's date comes from the text or the human.

  Check that the "Schema mentions PDFs" test passes for every language rendering.
- [x] 5.3 Update `templates/workflows/ingest.md`:
  - the argument hint includes `.pdf`;
  - step 1 says to stop and report on `multi_column` and `no_text_layer`;
  - step 2 says to read long raw files section by section and use References only to look up cited works;
  - step 4 says to ask the human for a missing PDF date.

  Check that the "Ingest workflow guides long papers" test passes, and that the Claude command and the Kimi skill bodies are still identical.
- [x] 5.4 Regenerate `templates/known_hashes.json` with `scripts/known_hashes.py`. Check that `test_registry_covers_current_templates` passes and that an upgrade test shows an untouched old `.gitignore` being `updated`.

## 6. Documentation and verification

- [x] 6.1 Update `README.md`, where it lists supported sources, to cover PDF capture and the git-ignored originals. Check by reading the section.
- [x] 6.2 Run the full test suite and confirm it passes with no new warnings.
- [x] 6.3 Manual check in a throwaway vault in the scratchpad (never a real vault, nothing committed):
  - capture the Levin paper and the human's second single-column paper;
  - compare each body with the PDF: title, sections, captions, footnotes, references, no page numbers;
  - report the findings to the human before archiving.
