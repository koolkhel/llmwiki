"""«Суть времени» news digests on rossaprimavera.ru: split an issue into dated items. Read-only.

Specific to this one newspaper's markup: `h3` sections, `p.block_date` datelines
("КУРСК, 18 сентября — РБК"), `p.quote` paragraphs quoted from the outlet and
`p.block_comment` paragraphs with the editorial comment.
"""

from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlsplit

from .errors import WikiError
from .fetch import as_date

FORMAT = "rp-digest"
DOMAIN = "rossaprimavera.ru"

MONTHS = {m: i for i, m in enumerate(
    ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
     "ноября", "декабря"), start=1)}
_DATELINE = re.compile(r"^(?P<place>.+?),\s*(?P<day>\d{1,2})\s+(?P<month>[а-яё]+)\s*[—–-]\s*(?P<outlet>.+)$",
                       re.I)
_ISSUE = re.compile(r"«(?P<name>[^«»]+)»\s*№\s*(?P<num>\d+)")
_HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.I)
_HAS_DATELINE = re.compile(rb"<p\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bblock_date\b", re.I)
_SKIP_TAGS = ("script", "style", "iframe", "noscript")


def is_rp_url(url: str | None) -> bool:
    host = (urlsplit(url).hostname or "").lower() if url else ""
    return host == DOMAIN or host.endswith("." + DOMAIN)


def looks_like_digest(url: str | None, html: bytes) -> bool:
    """Capture-time check: a rossaprimavera.ru page with at least one dateline paragraph."""
    return is_rp_url(url) and bool(_HAS_DATELINE.search(html))


def _space(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _classes(el) -> list[str]:
    c = el.get("class") or []
    return c.split() if isinstance(c, str) else list(c)


def _text(p) -> str:
    """Paragraph text with emphasis as `*…*` (whitespace kept outside the markers)."""
    for em in p.find_all(["em", "i"]):
        t = em.get_text().replace("\xa0", " ")
        inner = t.strip()
        if not inner:
            em.replace_with(t)
            continue
        lead = t[: len(t) - len(t.lstrip())]
        trail = t[len(t.rstrip()):]
        em.replace_with(f"{lead}*{inner}*{trail}")
    return _space(p.get_text())


def _service_block(cls: list[str]) -> bool:
    """Advertising and embedded promo widgets (not `widget article`, which wraps the article itself)."""
    return "ad_container" in cls or ("widget" in cls and "embed" in cls)


def _clean_outlet(s: str) -> str:
    s = s.strip()
    for a, b in (("«", "»"), ('"', '"'), ("“", "”")):
        if len(s) > 2 and s.startswith(a) and s.endswith(b) and a not in s[1:-1] and b not in s[1:-1]:
            return s[1:-1].strip()
    return s


def item_date(day: int, month: int, issue: dt.date) -> dt.date:
    """The dateline's day and month in the issue's year, or the year before if that is after the issue."""
    d = dt.date(issue.year, month, day)
    return d if d <= issue else dt.date(issue.year - 1, month, day)


def parse_dateline(text: str, issue: dt.date) -> dict | None:
    m = _DATELINE.match(text)
    if not m or m.group("month").lower() not in MONTHS:
        return None
    try:
        date = item_date(int(m.group("day")), MONTHS[m.group("month").lower()], issue)
    except ValueError:  # e.g. 31 февраля
        return None
    return {"place": m.group("place").strip(), "date": date.isoformat(), "outlet": _clean_outlet(m.group("outlet"))}


def _common_ancestor(els):
    paths = [list(reversed([e, *e.parents])) for e in els]
    common = None
    for level in zip(*paths):
        if all(x is level[0] for x in level):
            common = level[0]
        else:
            break
    return common


def parse_html(html: bytes | str, issue_published: object) -> dict:
    """Issue and items of a digest page. Raises `not_rp_digest` / `no_issue_date`."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all(True):
        if el.decomposed:
            continue
        if (el.name in _SKIP_TAGS or el.has_attr("hidden") or _HIDDEN_STYLE.search(el.get("style") or "")
                or _service_block(_classes(el))):
            el.decompose()
    datelines = [p for p in soup.find_all("p") if "block_date" in _classes(p)]
    if not datelines:
        raise WikiError("not_rp_digest", "No digest datelines (p.block_date) in the page; not an rp digest.")
    issue_day = as_date(issue_published)
    if issue_day is None:
        raise WikiError("no_issue_date", "The issue date is unknown (no `published` in the raw file or the page).")

    root = _common_ancestor(datelines)
    if root is datelines[0]:  # a single dateline: walk its container
        root = root.parent
    # The issue name and number («Суть времени» №682) are in the page text before the first dateline.
    header = "".join(reversed([str(s) for s in datelines[0].find_all_previous(string=True)]))
    m = _ISSUE.search(_space(header))

    items: list[dict] = []
    unassigned: list[dict] = []
    problems: list[dict] = []
    section: str | None = None
    current: dict | None = None
    for el in root.find_all(["h3", "p"]):
        if el.name == "h3":
            section = _space(el.get_text()) or None
            current = None
            continue
        cls = _classes(el)
        if "block_date" in cls:
            dateline = _space(el.get_text())
            parsed = parse_dateline(dateline, issue_day)
            current = {"n": len(items) + 1, "section": section, "dateline": dateline,
                       "place": None, "date": None, "outlet": None, "quote": [], "comment": None}
            if parsed:
                current.update(parsed)
            else:
                problems.append({"code": "bad_dateline", "item": current["n"],
                                 "message": f"Item {current['n']}: cannot read the date in {dateline!r}."})
            items.append(current)
        elif "quote" in cls or "block_comment" in cls:
            kind = "quote" if "quote" in cls else "comment"
            text = _text(el)
            if not text:
                continue
            if current is None:
                unassigned.append({"section": section, "kind": kind, "text": text})
                problems.append({"code": "unassigned_text",
                                 "message": f"A {kind} paragraph before any dateline in section {section!r}."})
            elif kind == "quote":
                current["quote"].append(text)
            else:
                current["comment"] = [*(current["comment"] or []), text]
    return {
        "issue": {
            "newspaper": m.group("name").strip() if m else None,
            "number": int(m.group("num")) if m else None,
            "published": str(issue_published) if not isinstance(issue_published, str) else issue_published,
        },
        "items": items,
        "unassigned": unassigned,
        "problems": problems,
    }


def source_items(vault, raw_arg: str) -> dict:
    """`wiki source-items-rp <raw>`."""
    from .pages import resolve_raw_arg
    from .sources import iter_raw

    rel = resolve_raw_arg(vault, raw_arg)
    return items_for_raw(vault, next(r for r in iter_raw(vault) if r.rel == rel))


def render_text(res: dict) -> str:
    i = res["issue"]
    name = f"«{i['newspaper']}» №{i['number']}" if i.get("number") else i.get("title")
    lines = [f"{name}, {str(i['published'])[:10]}: {len(res['items'])} item(s)"]
    for it in res["items"]:
        where = f"{it['place']} — {it['outlet']}" if it["place"] else it["dateline"]
        mark = "  [comment]" if it["comment"] else ""
        lines.append(f"{it['n']:>3}  {it['date'] or 'no date   '}  {where}{mark}")
    lines += [f"problem: {p['message']}" for p in res["problems"]]
    return "\n".join(lines)


def items_for_raw(vault, raw) -> dict:
    """Parse a raw file's stored original. Raises WikiError."""
    from .sources import derive_meta

    m = raw.meta or {}
    orig_rel = m.get("original_file")
    orig = vault.root / orig_rel if isinstance(orig_rel, str) and orig_rel else None
    if orig is None or not orig.is_file():
        raise WikiError("no_original", f"{raw.rel} has no stored original HTML (raw/.orig).", path=raw.rel)
    published = m.get("published")
    if as_date(published) is None:
        derived, _ = derive_meta(vault, raw)
        published = (derived or {}).get("published")
    res = parse_html(orig.read_bytes(), published)
    res["issue"] = {"title": raw.title, **res["issue"]}
    return {"path": raw.rel, "format": m.get("format"), **res}
