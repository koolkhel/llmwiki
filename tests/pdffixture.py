"""Synthetic PDF files for the capture-pdf tests: a tiny hand-written PDF 1.4 writer.

Text is placed at explicit positions and sizes in the standard Type 1 fonts, so
tests control exactly what layout signals the extractor sees. All text is invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

FONTS = {"R": "Times-Roman", "B": "Times-Bold", "H": "Helvetica"}
PAGE_W, PAGE_H = 612, 792  # US Letter


@dataclass
class Page:
    items: list[tuple[float, float, float, str, str]] = field(default_factory=list)  # x, y, size, font, text
    graphics: list[str] = field(default_factory=list)  # raw content operators (e.g. an image-like box)

    def text(self, x: float, y: float, s: str, size: float = 12, font: str = "R") -> "Page":
        self.items.append((x, y, size, font, s))
        return self

    def run(self, x: float, y: float, parts: list[tuple[str, float, str, float]]) -> "Page":
        """Consecutive pieces of one line: (text, size, font, rise) placed by their real widths."""
        for text, size, font, rise in parts:
            self.text(x, y + rise, text, size=size, font=font)
            x += width(text, size, font)
        return self

    def vertical(self, x: float, y: float, s: str, size: float = 10) -> "Page":
        """Text rotated 90 degrees, like arXiv's margin stamp."""
        self.graphics.append(f"BT /FR {size} Tf 0 1 -1 0 {x} {y} Tm ({_esc(s)}) Tj ET")
        return self

    def box(self, x: float, y: float, w: float, h: float) -> "Page":
        self.graphics.append(f"0.5 g {x} {y} {w} {h} re f")
        return self


def width(text: str, size: float, font: str = "R") -> float:
    from pdfminer.fontmetrics import FONT_METRICS

    widths = FONT_METRICS[FONTS[font]][1]
    return sum(widths.get(c, 500) for c in text) * size / 1000


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content(page: Page) -> bytes:
    ops = list(page.graphics)
    for x, y, size, font, s in page.items:
        ops.append(f"BT /F{font} {size} Tf {x} {y} Td ({_esc(s)}) Tj ET")
    return "\n".join(ops).encode("cp1252")


def pdf_bytes(pages: list[Page], info: dict[str, str] | None = None) -> bytes:
    objs: list[bytes] = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    font_ids = {k: add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{v} /Encoding /WinAnsiEncoding >>".encode())
                for k, v in FONTS.items()}
    fonts = " ".join(f"/F{k} {i} 0 R" for k, i in font_ids.items())
    pages_id = len(objs) + 1 + 2 * len(pages)  # reserved after the page/content pairs
    kids = []
    for p in pages:
        data = _content(p)
        cid = add(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
        kids.append(add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                        f"/Resources << /Font << {fonts} >> >> /Contents {cid} 0 R >>".encode()))
    assert add(f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()) \
        == pages_id
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    info_id = None
    if info:
        info_id = add(("<< " + " ".join(f"/{k} ({_esc(v)})" for k, v in info.items()) + " >>").encode("cp1252"))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    trailer = f"<< /Size {len(objs) + 1} /Root {catalog} 0 R" + (f" /Info {info_id} 0 R" if info_id else "") + " >>"
    out += b"trailer\n" + trailer.encode() + b"\nstartxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


def write_pdf(path: Path, pages: list[Page], info: dict[str, str] | None = None) -> Path:
    path.write_bytes(pdf_bytes(pages, info))
    return path


# --- a synthetic single-column paper ----------------------------------------------------

LEFT, RIGHT, LEAD = 72, 540, 14.4
TITLE = "Synthetic Gardens of Imaginary Minds"
BODY_WORDS = ("the invented garden grows patterns that nobody planted and every visitor sees "
              "a different hedge maze of made up ideas").split()


def _filler(n: int, start: int = 0) -> list[str]:
    """Body lines of invented prose, each about one full text width."""
    lines = []
    for i in range(n):
        words = [BODY_WORDS[(start + i * 3 + j) % len(BODY_WORDS)] for j in range(13)]
        lines.append(" ".join(words))
    return lines


def paper_pages(page_numbers: bool = True, body_size: float = 12) -> list[Page]:
    """Three pages: title block, sections, a caption, a footnote, a cross-page paragraph, references."""
    s = body_size
    lead = s * 1.2
    p1 = Page()
    p1.text(110, 720, TITLE, size=s * 1.6, font="B")
    sup = s * 0.6
    p1.run(200, 690, [("Anna Example", s, "R", 0), ("1", sup, "R", s * 0.35), (", Boris Sample", s, "R", 0),
                      ("2", sup, "R", s * 0.35)])
    p1.text(150, 672, "1 Imaginary Institute; 2 Nowhere College", size=s * 0.8)
    p1.text(150, 658, "https://doi.org/10.1234/abcd.5678", size=s * 0.8)
    p1.text(LEFT, 630, "Abstract", size=s, font="B")
    y = 630 - lead
    for line in _filler(3):
        p1.text(LEFT, y, line, size=s)
        y -= lead
    y -= lead
    p1.text(LEFT, y, "1. Overview", size=s, font="B")
    y -= lead
    p1.run(LEFT + 36, y, [("First paragraph of the overview speaks about categories", s, "R", 0),
                          ("1", sup, "R", s * 0.35), (" and more of", s, "R", 0)])
    y -= lead
    for line in _filler(4, 5):
        p1.text(LEFT, y, line, size=s)
        y -= lead
    p1.text(LEFT, y, "and it ends here with a full stop.", size=s)
    y -= lead
    p1.text(LEFT + 36, y, "Second paragraph runs to the bottom of the page and keeps going with", size=s)
    y -= lead
    while y > 140:
        p1.text(LEFT, y, _filler(1, int(y))[0], size=s)
        y -= lead
    p1.text(LEFT, y, "a sentence that is cut by the page break and continues", size=s)
    p1.text(LEFT, 90, "1 A footnote about invented categories.", size=s * 0.8)
    if page_numbers:
        p1.text(303, 40, "1", size=s)

    p2 = Page()
    y = 720
    p2.text(LEFT, y, "on the following page without any break at all.", size=s)
    y -= lead * 2
    p2.box(150, y - 200, 300, 190)
    y -= 215
    p2.text(LEFT, y, "Figure 1: An invented hedge maze drawn in grey.", size=s * 0.8)
    y -= lead * 2
    p2.text(LEFT, y, "2. Discussion", size=s, font="B")
    y -= lead
    for line in _filler(3, 11):
        p2.text(LEFT, y, line, size=s)
        y -= lead
    p2.text(LEFT, y, "and the discussion of the invented garden ends with a short remark about hyphen-", size=s)
    y -= lead
    p2.text(LEFT, y, "ation in gardens.", size=s)
    if page_numbers:
        p2.text(303, 40, "2", size=s)

    p3 = Page()
    y = 720
    p3.text(LEFT, y, "References", size=s, font="B")
    y -= lead * 1.5
    refs = [("1.", ["Example A, Sample B. Gardens without gardeners. Journal of Invented Things,",
                    "12(3):45-67, 2020."]),
            ("2.", ["Nobody C. A short note on mazes. Imaginary Letters, 1:1-2, 2021."]),
            ("10.", ["Sample B. Very long title about hedges that wraps onto a second line of the",
                     "reference list, Proceedings of Nothing, 2022."])]
    for num, lines in refs:
        p3.text(LEFT, y, num, size=s)
        for line in lines:
            p3.text(LEFT + 36, y, line, size=s)
            y -= lead
    if page_numbers:
        p3.text(303, 40, "3", size=s)
    return [p1, p2, p3]


def two_column_pages() -> list[Page]:
    pages = []
    for _ in range(2):
        p = Page()
        y = 720
        for line in _filler(30):
            p.text(LEFT, y, line[:40], size=10)
            p.text(320, y, line[-40:], size=10)
            y -= 12
        pages.append(p)
    return pages


def image_only_pages() -> list[Page]:
    return [Page().box(50, 50, 500, 700), Page().box(50, 50, 500, 700)]
