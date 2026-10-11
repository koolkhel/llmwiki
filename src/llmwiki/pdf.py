"""Single-column PDF papers to markdown, from the page layout. Read-only, no vault knowledge.

pdfminer.six gives every character with its font, size and position. Characters are
rebuilt into visual lines (by baseline, left to right), each line is classified by
font, size and position relative to the document's own body text, and lines are
joined into paragraphs. Anything not recognised stays a plain paragraph: no text is
dropped except page numbers and running headers/footers.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .errors import WikiError

FORMAT = "pdf"
SUP_OPEN, SUP_CLOSE = "", ""  # superscript markers inside line text
_BOLD = re.compile(r"bold|black|heavy|semibold|demi", re.I)
_LIGATURES = {chr(c): unicodedata.normalize("NFKC", chr(c)) for c in range(0xFB00, 0xFB07)}
_PAGE_NUM = re.compile(r"^(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?$", re.I)
_CAPTION = re.compile(r"^(?:Figure|Fig\.|Table)\s*\d+[A-Za-z]?(?:[.:]|\s)", re.I)
_REFS_HEADING = re.compile(r"^(?:\d+\.?\s*)?(?:references|bibliography|literature(?: cited)?|works cited)$", re.I)
_TOC_HEADING = re.compile(r"^(?:table of )?contents$", re.I)
_TOC_ENTRY = re.compile(r"\S\s*(?:\.\s*){0,}\s\d{1,4}$")  # "1 Introduction 5", "Intro . . . . 5"
_REF_START = re.compile(r"^(?:\[\d+\]|\d+\.)\s")
_FOOT_START = re.compile(r"^" + SUP_OPEN + r"?(\d{1,3})" + SUP_CLOSE + r"?\s*(.*)$", re.S)
_SUP = re.compile(SUP_OPEN + r"(.*?)" + SUP_CLOSE, re.S)
_ITEM = re.compile(r"^(?:\(?(?:[a-z]|[ivx]{1,4}|\d{1,2})[.)]|[•▪◦o\-–])\s")  # a list item start
_BULLET = re.compile(r"^[•▪◦o]\s+")
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)")
_SENTENCE_END = re.compile(r"[.!?:;][\"'»”)\]]*$")
_NAME_WORD = re.compile(r"^[^\W\d_]+(?:[-'’.][^\W\d_]*)*\.?$")
_NOT_NAME = re.compile(r"\b(?:institute|university|college|department|school|laboratory|lab|center|centre|"
                       r"faculty|abstract|introduction|journal|preprint|email|correspondence)\b", re.I)
_PLACEHOLDER_TITLE = re.compile(r"^(?:untitled|microsoft word\b.*|paper\s*v?\d*|document\s*\d*|draft\s*\d*)$", re.I)


@dataclass
class Char:
    text: str
    size: float
    bold: bool
    x0: float
    x1: float
    y0: float


@dataclass
class Line:
    page: int
    y: float
    x0: float
    x1: float
    size: float
    bold: bool
    text: str
    kind: str = "body"
    page_height: float = 792.0


@dataclass
class PdfDoc:
    title: str
    authors: list[str]
    doi: str | None
    pages: int
    body: str
    extractor: str
    warnings: list[str] = field(default_factory=list)


def extractor_name() -> str:
    import pdfminer

    return f"pdfminer.six {pdfminer.__version__}"


# --- reading --------------------------------------------------------------------------


def _decode(v: object) -> str | None:
    from pdfminer.pdftypes import resolve1
    from pdfminer.utils import decode_text

    v = resolve1(v)
    if isinstance(v, bytes):
        v = decode_text(v)
    return " ".join(v.split()) if isinstance(v, str) and v.strip() else None


def _open(path: Path) -> tuple[dict, list]:
    """(info dict, [(page width, page height, [Char])]). Raises pdf_encrypted / pdf_unreadable."""
    from pdfminer.layout import LAParams, LTChar, LTPage
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.pdfdocument import PDFDocument, PDFEncryptionError, PDFPasswordIncorrect
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser

    def walk(obj):
        if isinstance(obj, LTChar):
            yield obj
        elif hasattr(obj, "__iter__"):
            for o in obj:
                yield from walk(o)

    try:
        with path.open("rb") as f:
            doc = PDFDocument(PDFParser(f))
            info = {k: _decode(v) for d in (doc.info or []) for k, v in d.items()}
            rm = PDFResourceManager()
            dev = PDFPageAggregator(rm, laparams=LAParams())
            interp = PDFPageInterpreter(rm, dev)
            pages = []
            for page in PDFPage.create_pages(doc):
                interp.process_page(page)
                lt: LTPage = dev.get_result()
                # Rotated text (e.g. arXiv's vertical margin stamp) is not part of the reading flow.
                chars = [Char(c.get_text(), round(c.size, 2), bool(_BOLD.search(c.fontname or "")),
                              c.x0, c.x1, c.y0) for c in walk(lt) if c.upright]
                pages.append((lt.width, lt.height, chars))
    except (PDFPasswordIncorrect, PDFEncryptionError) as e:
        raise WikiError("pdf_encrypted", f"{path.name}: the PDF is encrypted and needs a password ({e}).",
                        path=str(path)) from None
    except Exception as e:  # noqa: BLE001 - any parser failure means the file is not usable
        if type(e).__name__ in ("PDFPasswordIncorrect", "PDFEncryptionError"):
            raise WikiError("pdf_encrypted", f"{path.name}: the PDF is encrypted and needs a password.",
                            path=str(path)) from None
        raise WikiError("pdf_unreadable", f"{path.name}: not a readable PDF ({type(e).__name__}: {e}).",
                        path=str(path)) from None
    return info, pages


def _weighted_mode(pairs) -> float:
    c = Counter()
    for value, weight in pairs:
        c[value] += weight
    return c.most_common(1)[0][0] if c else 0.0


def _rows(chars: list[Char], body: float) -> list[list[tuple[Char, bool]]]:
    """Visual lines: (char, is_superscript) lists, top to bottom; raised small chars join their line."""
    rows: list[dict] = []
    normal = sorted((c for c in chars if c.size >= 0.75 * body), key=lambda c: (-c.y0, c.x0))
    small = sorted((c for c in chars if c.size < 0.75 * body), key=lambda c: (-c.y0, c.x0))
    for c in normal:
        for r in rows:
            if abs(c.y0 - r["y"]) <= 0.25 * max(c.size, r["size"]):
                r["chars"].append((c, False))
                r["size"] = max(r["size"], c.size)
                r["x0"], r["x1"] = min(r["x0"], c.x0), max(r["x1"], c.x1)
                break
        else:
            rows.append({"y": c.y0, "size": c.size, "chars": [(c, False)], "x0": c.x0, "x1": c.x1})
    for c in small:
        host = next((r for r in rows if r["size"] >= 0.75 * body and r["y"] < c.y0 < r["y"] + 0.8 * r["size"]
                     and r["x0"] - r["size"] <= c.x0 <= r["x1"] + r["size"]), None)
        if host:
            host["chars"].append((c, True))
            continue
        for r in rows:
            if abs(c.y0 - r["y"]) <= 0.25 * max(c.size, r["size"]):
                r["chars"].append((c, False))
                break
        else:
            rows.append({"y": c.y0, "size": c.size, "chars": [(c, False)], "x0": c.x0, "x1": c.x1})
    rows.sort(key=lambda r: -r["y"])
    return [sorted(r["chars"], key=lambda t: t[0].x0) for r in rows]


def _line_text(chars: list[tuple[Char, bool]]) -> str:
    out: list[str] = []
    last: Char | None = None
    in_sup = False
    for c, sup in chars:
        if last is not None and c.x0 - last.x1 > 0.2 * min(c.size, last.size) and not sup:
            out.append(" ")
        if sup and not in_sup:
            out.append(SUP_OPEN)
        elif not sup and in_sup:
            out.append(SUP_CLOSE)
        in_sup = sup
        out.append(_LIGATURES.get(c.text, c.text))
        last = c
    if in_sup:
        out.append(SUP_CLOSE)
    text = re.sub(r"[ \t  -​　]+", " ", "".join(out))
    text = re.sub(SUP_OPEN + r"\s*(.*?)\s*" + SUP_CLOSE, lambda m: SUP_OPEN + m.group(1) + SUP_CLOSE, text)
    return unicodedata.normalize("NFC", text.strip())


def _lines(pages: list, body: float) -> list[Line]:
    out = []
    for i, (_w, h, chars) in enumerate(pages):
        for row in _rows(chars, body):
            main = [c for c, sup in row if not sup and c.text.strip()] or [c for c, _ in row]
            text = _line_text(row)
            if not text:
                continue
            out.append(Line(
                page=i, y=statistics.median(c.y0 for c in main), x0=min(c.x0 for c in main),
                x1=max(c.x1 for c in main), size=_weighted_mode((c.size, 1) for c in main),
                bold=sum(c.bold for c in main) > len(main) / 2, text=text, page_height=h))
    return out


# --- checks -----------------------------------------------------------------------------


def _check_text_layer(pages: list, path: Path) -> None:
    n = sum(1 for _w, _h, chars in pages for c in chars if c.text.strip())
    if n < 50 or n < 20 * len(pages):
        raise WikiError("no_text_layer", f"{path.name}: no text layer (a scanned PDF?); OCR is not supported.",
                        path=str(path))


def _check_single_column(pages: list, body: float, path: Path) -> None:
    """Two columns: body lines with text on both halves of the text area almost never cross its middle."""
    xs = [c for _w, _h, chars in pages for c in chars if abs(c.size - body) <= 0.6 and c.text.strip()]
    if not xs:
        return
    left, right = min(c.x0 for c in xs), max(c.x1 for c in xs)
    mid = (left + right) / 2
    both = crossing = 0
    for _w, _h, chars in pages:
        for row in _rows([c for c in chars if abs(c.size - body) <= 0.6], body):
            cs = [c for c, _ in row if c.text.strip()]
            if any(c.x1 < mid for c in cs) and any(c.x0 > mid for c in cs):
                both += 1
                ordered = sorted(cs, key=lambda c: c.x0)
                gaps = [(a.x1, b.x0) for a, b in zip(ordered, ordered[1:])]
                if not any(a <= mid + 4 and b >= mid - 4 and b - a > 1.5 * body for a, b in gaps):
                    crossing += 1
    if both >= 10 and crossing < 0.1 * both:
        raise WikiError("multi_column", f"{path.name}: the text is laid out in columns; only single-column "
                        "PDFs are supported.", path=str(path))


# --- classification -----------------------------------------------------------------------


def _classify(lines: list[Line], body: float, n_pages: int) -> None:
    def zone(ln: Line) -> bool:
        return ln.y < 0.08 * ln.page_height or ln.y > 0.92 * ln.page_height

    for ln in lines:
        if zone(ln) and _PAGE_NUM.match(_SUP.sub("", ln.text)):
            ln.kind = "page_number"
    if n_pages >= 3:
        keys = Counter((re.sub(r"\d+", "#", ln.text), round(ln.y / 3)) for ln in lines
                       if ln.kind == "body" and (ln.y < 0.12 * ln.page_height or ln.y > 0.88 * ln.page_height))
        for ln in lines:
            if (ln.kind == "body" and keys.get((re.sub(r"\d+", "#", ln.text), round(ln.y / 3)), 0) >= max(2, n_pages / 2)
                    and (ln.y < 0.12 * ln.page_height or ln.y > 0.88 * ln.page_height)):
                ln.kind = "running"

    first = [ln for ln in lines if ln.page == 0 and ln.kind == "body" and ln.y > ln.page_height / 2]
    if first:
        top = max(ln.size for ln in first)
        if top >= 1.1 * body:
            started = False
            for ln in lines:
                if ln.page != 0 or ln.kind != "body":
                    continue
                if abs(ln.size - top) < 0.5 and (not started or ln.kind == "body"):
                    ln.kind, started = "title", True
                elif started:
                    break

    marker_numbers: set[str] = set()
    _bold_title(lines, body)
    in_refs = in_toc = False
    page_body_bottom: dict[int, float] = {}
    for ln in lines:
        if ln.kind == "body" and abs(ln.size - body) <= 0.6:
            page_body_bottom[ln.page] = min(page_body_bottom.get(ln.page, 1e9), ln.y)
    prev: Line | None = None
    for ln in lines:
        if ln.kind != "body":
            prev = ln if ln.kind not in ("page_number", "running") else prev
            continue
        plain = _SUP.sub("", ln.text)
        small = ln.size < 0.95 * body
        if in_toc and _TOC_ENTRY.search(plain):
            ln.kind = "toc"
        elif small and _CAPTION.match(plain):
            ln.kind = "caption"
        elif (small and prev is not None and prev.kind == "caption" and prev.page == ln.page
              and abs(prev.size - ln.size) < 0.4 and prev.y - ln.y < 2 * ln.size):
            ln.kind = "caption"
        elif small and ln.y < page_body_bottom.get(ln.page, -1):
            m = _FOOT_START.match(ln.text)
            if m and m.group(1) in marker_numbers:
                ln.kind = "footnote"
            elif prev is not None and prev.kind in ("footnote", "footnote_cont") and prev.page == ln.page:
                ln.kind = "footnote_cont"
        elif (ln.bold or ln.size >= 1.15 * body) and len(plain) < 120 \
                and not (in_refs and (plain[:1].isdigit() or plain.startswith("["))):
            ln.kind = "heading"
            in_refs = bool(_REFS_HEADING.match(plain.strip()))
            in_toc = bool(_TOC_HEADING.match(plain.strip()))
        elif in_refs:
            ln.kind = "reference"
        if ln.kind in ("body", "reference"):
            marker_numbers.update(m for m in _SUP.findall(ln.text) if m.isdigit())
        prev = ln
    # Runs of more than two bold lines are bold paragraphs, not headings.
    run: list[Line] = []
    for ln in [*lines, None]:
        if ln is not None and ln.kind == "heading" and (not run or (run[-1].page == ln.page
                                                                     and run[-1].y - ln.y < 2 * ln.size)):
            run.append(ln)
            continue
        if len(run) > 2:
            for r in run:
                r.kind = "body"
        run = [ln] if ln is not None and ln.kind == "heading" else []


def _bold_title(lines: list[Line], body: float) -> None:
    """No larger title: the first bold line(s) at the top of page 1, unless they are a section heading."""
    if any(ln.kind == "title" for ln in lines):
        return
    for i, ln in enumerate(lines):
        if ln.page != 0 or ln.y < ln.page_height / 2:
            return
        if ln.kind != "body":
            continue
        plain = _SUP.sub("", ln.text).strip()
        if not ln.bold:  # the title is the first thing on the page
            return
        if re.match(r"^(?:\d+\.?\s|abstract\b|introduction\b|(?:table of )?contents\b|references\b)", plain, re.I):
            return
        run = [ln]
        for nxt in lines[i + 1:]:
            if nxt.page == 0 and nxt.bold and nxt.kind == "body" and run[-1].y - nxt.y < 2 * nxt.size:
                run.append(nxt)
            else:
                break
        if len(run) <= 3:
            for r in run:
                r.kind = "title"
        return


# --- assembly -------------------------------------------------------------------------------


def _join(a: str, b: str) -> str:
    if re.search(r"[a-zà-ÿа-яё]-$", a) and re.match(r"[a-zà-ÿа-яё]", b):
        return a[:-1] + b
    return f"{a} {b}"


def _body_lead(lines: list[Line], body: float) -> float:
    diffs = [a.y - b.y for a, b in zip(lines, lines[1:])
             if a.page == b.page and a.kind == b.kind == "body" and 0 < a.y - b.y < 3 * body]
    return statistics.median(diffs) if diffs else 1.2 * body


def _assemble(lines: list[Line], body: float) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Blocks [(kind, text)] in reading order, and footnote definitions {number: text}."""
    lead = _body_lead(lines, body)
    body_lines = [ln for ln in lines if ln.kind == "body" and abs(ln.size - body) <= 0.6]
    right = sorted(ln.x1 for ln in body_lines)[int(0.9 * (len(body_lines) - 1))] if body_lines else 540
    left = sorted(ln.x0 for ln in body_lines)[int(0.1 * (len(body_lines) - 1))] if body_lines else 72
    refs = [ln for ln in lines if ln.kind == "reference"]
    ref_left = min((ln.x0 for ln in refs), default=0)
    hanging = sum(ln.x0 > ref_left + 3 for ln in refs) >= len(refs) / 4 and any(ln.x0 <= ref_left + 2 for ln in refs)
    at_left = [ln for ln in refs if ln.x0 <= ref_left + 2]
    numbered = bool(at_left) and sum(bool(_REF_START.match(_SUP.sub("", ln.text))) for ln in at_left) >= 0.8 * len(at_left)
    blocks: list[tuple[str, str]] = []
    floats: list[list[str]] = []
    notes: dict[str, str] = {}
    cur: dict | None = None  # the open block: kind, text, last line
    note_key: str | None = None
    last_caption: list | None = None  # [kind, text] of the caption being continued

    def close() -> None:
        nonlocal cur
        if cur:
            blocks.append((cur["kind"], cur["text"]))
            cur = None
        blocks.extend((f[0], f[1]) for f in floats)
        floats.clear()

    for ln in lines:
        k = ln.kind
        if k in ("page_number", "running"):
            continue
        if k in ("footnote", "footnote_cont"):
            if k == "footnote":
                m = _FOOT_START.match(ln.text)
                note_key = m.group(1)
                notes[note_key] = m.group(2).strip()
            elif note_key:
                notes[note_key] = _join(notes[note_key], ln.text)
            continue
        if k == "caption":
            if last_caption is not None and not _CAPTION.match(_SUP.sub("", ln.text)):
                last_caption[1] = _join(last_caption[1], ln.text)
            else:
                last_caption = ["caption", ln.text]
                floats.append(last_caption)
                if cur is None or cur["kind"] != "body" or _SENTENCE_END.search(cur["text"]):
                    close()
            continue
        last_caption = None
        prev = cur["last"] if cur else None
        if cur and cur["kind"] == k and k in ("title", "heading") and prev.page == ln.page \
                and prev.y - ln.y < 2 * ln.size:
            cur["text"], cur["last"] = _join(cur["text"], ln.text), ln
            continue
        if cur and cur["kind"] == k == "reference":
            prev = cur["last"]
            if hanging:  # an entry starts at the left edge, its continuation lines are indented
                start = ln.x0 <= ref_left + 2 and (not numbered or bool(_REF_START.match(_SUP.sub("", ln.text))))
            else:
                start = bool(_REF_START.match(_SUP.sub("", ln.text))) or (
                    prev.page == ln.page and prev.y - ln.y > 1.5 * lead)
            if start:
                close()
                cur = {"kind": k, "text": ln.text, "last": ln}
            else:
                cur["text"], cur["last"] = _join(cur["text"], ln.text), ln
            continue
        if cur and cur["kind"] == k == "body":
            # A line under 3/4 of the text width ends a paragraph (or is a line break: addresses,
            # verse). A paragraph ends with sentence punctuation, then a short line, an indented next line,
            # or (across a page) a next line that doesn't continue in lowercase. An indent after a
            # line without punctuation is a hanging indent (list items, quotes) and continues.
            indented = ln.x0 > prev.x0 + 0.8 * body
            ended = bool(_SENTENCE_END.search(prev.text))
            item = bool(_ITEM.match(ln.text))
            short = prev.x1 - prev.x0 < 0.75 * (right - left)
            if prev.page == ln.page:
                gap = prev.y - ln.y > 1.5 * lead
                # Short lines aligned with each other (verse, epigraphs, address blocks) stay one
                # block with their line breaks.
                aligned = abs(ln.x0 - prev.x0) < 2 or abs(ln.x1 - prev.x1) < 2
                if short and not gap and not ended and not item and aligned and abs(ln.size - prev.size) < 0.5:
                    cur["text"], cur["last"] = cur["text"] + "\n" + ln.text, ln
                    continue
                new = gap or short or (ended and (indented or prev.x1 < right - 2 * body or item))
            else:
                new = ended and (indented or item or not ln.text[:1].islower())
            if not new:
                cur["text"], cur["last"] = _join(cur["text"], ln.text), ln
                continue
        close()
        cur = {"kind": k, "text": ln.text, "last": ln}
    close()
    return blocks, notes


def _render(title: str, blocks: list[tuple[str, str]], notes: dict[str, str]) -> str:
    used: list[str] = []
    in_front = True  # before the first heading: superscripts are affiliations, not footnotes

    def marks(text: str) -> str:
        def sub(m: re.Match) -> str:
            n = m.group(1)
            if not n.strip():
                return " "
            if n in notes and not in_front:
                if n not in used:
                    used.append(n)
                return f"[^{n}]"
            return f"<sup>{n}</sup>"
        return _SUP.sub(sub, text)

    out = [f"# {title}"]
    prev_kind = None
    for kind, text in blocks:
        if kind == "title":
            continue
        if kind == "heading":
            in_front = False
        text = "\n".join(t.strip() for t in marks(text).split("\n"))
        if kind == "heading":
            out.append(f"## {text}")
        elif kind == "caption":
            out.append(f"> {text}")
        elif kind == "toc":  # one tight list, without dot leaders
            entry = "- " + re.sub(r"(?:\s*\.){3,}\s*", " ", text)
            if prev_kind == "toc":
                out[-1] += "\n" + entry
            else:
                out.append(entry)
        elif kind == "body" and _BULLET.match(text):
            out.append(_BULLET.sub("- ", text, count=1))
        elif kind == "body" and re.match(r"[>#|]", text):  # not a quote/heading/table in markdown
            out.append("\\" + text)
        else:
            out.append(text)
        prev_kind = kind
    order = used + sorted((n for n in notes if n not in used), key=int)
    in_front = False
    if order:
        out.append("\n".join(f"[^{n}]: {marks(notes[n])}" for n in order))
    return "\n\n".join(out) + "\n"


# --- metadata --------------------------------------------------------------------------


def _is_name(s: str) -> bool:
    words = s.split()
    return 2 <= len(words) <= 5 and all(_NAME_WORD.match(w) for w in words) and not _NOT_NAME.search(s) \
        and any(w[:1].isupper() for w in words)


def _split_names(s: str) -> list[str]:
    s = _SUP.sub(",", s)
    parts = re.split(r"\s*(?:,|;|&|\band\b)\s*", s)
    names = [re.sub(r"[\d*†‡§¶]+$", "", p).strip() for p in parts]
    return [n for n in names if n]


def _names(s: str | None) -> list[str]:
    if not s:
        return []
    names = _split_names(s)
    return names if names and all(_is_name(n) for n in names) else []


def _page1_authors(lines: list[Line]) -> list[str]:
    p1 = [ln for ln in lines if ln.page == 0 and ln.kind not in ("page_number", "running")]
    try:
        start = max(i for i, ln in enumerate(p1) if ln.kind == "title") + 1
    except ValueError:
        return []
    out: list[str] = []
    for ln in p1[start:]:
        if ln.kind != "body":
            break
        names = _names(ln.text)
        if not names:
            break
        out += [n for n in names if n not in out]
    return out


def _title(lines: list[Line], info: dict, stem: str) -> str:
    t = " ".join(_SUP.sub("", ln.text) for ln in lines if ln.kind == "title").strip()
    if len(t) > 2 and t[0] in "“\"«" and t[-1] in "”\"»":
        t = t[1:-1].strip()
    if t:
        return t
    meta = info.get("Title")
    if meta and meta != stem and not _PLACEHOLDER_TITLE.match(meta):
        return meta
    return stem


def extract(path: Path) -> PdfDoc:
    """Extract a single-column PDF. Raises WikiError (pdf_unreadable, pdf_encrypted, no_text_layer, multi_column)."""
    info, pages = _open(path)
    _check_text_layer(pages, path)
    all_chars = [c for _w, _h, chars in pages for c in chars if c.text.strip()]
    body = _weighted_mode((round(c.size * 2) / 2, 1) for c in all_chars)
    _check_single_column(pages, body, path)
    lines = _lines(pages, body)
    _classify(lines, body, len(pages))
    title = _title(lines, info, path.stem)
    blocks, notes = _assemble(lines, body)
    page1 = " ".join(ln.text for ln in lines if ln.page == 0)
    doi = _DOI.search(page1)
    warnings = []
    cids = sum(ln.text.count("(cid:") for ln in lines)
    if cids:
        warnings.append(f"{cids} character(s) could not be mapped to text and appear as (cid:N).")
    return PdfDoc(
        title=title,
        authors=_names(info.get("Author")) or _page1_authors(lines),
        doi=doi.group(1).rstrip(".,;)]") if doi else None,
        pages=len(pages),
        body=_render(title, blocks, notes),
        extractor=extractor_name(),
        warnings=warnings,
    )
