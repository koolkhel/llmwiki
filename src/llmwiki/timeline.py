"""`wiki timeline`: the sources about a page (or by an author), in publication order. Read-only."""

from __future__ import annotations

import unicodedata

from .errors import WikiError
from .fetch import as_date, clean_authors, date_bound, format_date, instant, parse_date
from .links import Resolver, links_in_meta, page_links
from .morph import Analyzer, tokenize
from .naming import key, nfc
from .pages import Page, iter_pages
from .search import _author_names, _author_tier
from .sources import iter_raw
from .vault import Vault


def _find_page(pages: list[Page], arg: str) -> Page:
    a = nfc(arg.strip())
    by_rel = {p.rel: p for p in pages}
    for cand in (a, f"{a}.md", f"wiki/{a}", f"wiki/{a}.md"):
        if cand in by_rel:
            return by_rel[cand]
    matches = [p for p in pages if key(p.stem) == key(a)]
    if not matches:
        raise WikiError("page_not_found", f"No wiki page named {arg!r}.", page=arg)
    return matches[0]


def _date_of(page: Page, raw_published: dict[str, object]) -> tuple[object, str | None]:
    """(value to sort by, displayed date): the raw file's precise value when it agrees with the page."""
    page_day = as_date(page.published)
    raw_ref = (page.meta or {}).get("raw")
    raw_value = raw_published.get(raw_ref.strip().removeprefix("./")) if isinstance(raw_ref, str) else None
    raw_day = as_date(raw_value)
    if raw_day is not None and (page_day is None or raw_day == page_day):
        return raw_value, format_date(parse_date(raw_value))
    if page_day is not None:
        return page_day, page_day.isoformat()
    return None, None


def timeline(vault: Vault, page_arg: str | None = None, author: str | None = None,
             since: str | None = None, until: str | None = None) -> dict:
    if (page_arg is None) == (author is None):
        raise WikiError("usage_error", "Give either a page or --author.")
    lo = date_bound(since, end=False) if since is not None else None
    hi = date_bound(until, end=True) if until is not None else None
    pages = iter_pages(vault)
    sources = [p for p in pages if p.folder_type == "source"]

    if page_arg is not None:
        target = _find_page(pages, page_arg)
        resolver = Resolver(vault, pages)
        by_rel = {p.rel: p for p in pages}
        listed = {resolver.resolve(l.target) for l in links_in_meta({"sources": (target.meta or {}).get("sources")})}
        members = {p.rel for p in sources if p.rel in listed}
        members |= {p.rel for p in sources if p.rel != target.rel
                    and any(resolver.resolve(l.target) == target.rel for l in page_links(p))}
        chosen = [by_rel[r] for r in members]
        header = {"page": target.rel, "title": target.stem}
    else:
        an = Analyzer()
        words = [t.text for t in tokenize(unicodedata.normalize("NFC", author), compounds=False)]
        if not words:
            raise WikiError("empty_query", "--author must contain at least one word.")
        aliases_by_key = {key(p.stem): p.aliases for p in pages if p.aliases}
        chosen = []
        for p in sources:
            names = _author_names(p.meta)
            names += [a for n in names for a in aliases_by_key.get(key(n), [])]
            if _author_tier(names, words, an, exact_only=False):
                chosen.append(p)
        header = {"author": author}

    raw_published = {r.rel: r.published for r in iter_raw(vault) if r.published}
    entries = []
    for p in chosen:
        sort_value, shown = _date_of(p, raw_published)
        day = as_date(sort_value)
        if (lo or hi) and (day is None or (lo and day < lo) or (hi and day > hi)):
            continue
        a = (p.meta or {}).get("authors")
        entry = {
            "published": shown,
            "title": p.stem,
            "link": p.link,
            "path": p.rel,
            "authors": clean_authors(a) if isinstance(a, list) else [],
            "summary": p.summary,
            "_t": instant(sort_value),
        }
        if isinstance(outlet := (p.meta or {}).get("outlet"), str) and outlet:
            entry["outlet"] = outlet
        if shown is None:
            entry["undated"] = True
        entries.append(entry)
    entries.sort(key=lambda e: (e["_t"] is None, e["_t"].timestamp() if e["_t"] else 0, key(e["title"])))
    for e in entries:
        del e["_t"]
    dated = sum(1 for e in entries if not e.get("undated"))
    return {**header, "entries": entries, "counts": {"total": len(entries), "dated": dated,
                                                     "undated": len(entries) - dated}}


def render_text(res: dict) -> str:
    head = f"timeline: {res.get('title') or res.get('author')}"
    lines = [head]
    for e in res["entries"]:
        date = (e["published"] or "undated")[:10]
        who = f"  ({', '.join(e['authors'])})" if e["authors"] else ""
        lines.append(f"  {date:<10}  {e['link']}{who}  {e['summary']}".rstrip())
    c = res["counts"]
    lines.append(f"{c['total']} source(s), {c['undated']} undated")
    return "\n".join(lines)
