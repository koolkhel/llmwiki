"""Plain term search over wiki pages (or raw sources)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .errors import WikiError
from .naming import key
from .pages import iter_pages
from .sources import iter_raw
from .vault import Vault

SNIPPET_RADIUS = 80
TITLE_WEIGHT, META_WEIGHT, BODY_WEIGHT, BODY_CAP = 100, 10, 1, 5


def fold_with_map(s: str) -> tuple[str, list[int]]:
    """Case- and accent-folded text, plus a map from each folded char to its source index."""
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(s):
        for d in unicodedata.normalize("NFKD", ch):
            if unicodedata.combining(d):
                continue
            for f in d.casefold():
                out.append(f)
                idx.append(i)
    return "".join(out), idx


def fold(s: str) -> str:
    return fold_with_map(s)[0]


@dataclass
class _Doc:
    path: str
    title: str
    type: str
    summary: str
    tags: list[str]
    body: str


def _snippet(body: str, terms: list[str]) -> str:
    folded, idx = fold_with_map(body)
    hits = [p for p in (folded.find(t) for t in terms) if p >= 0]
    if not hits:
        return " ".join(body.split())[: 2 * SNIPPET_RADIUS]
    start = idx[min(hits)]
    lo, hi = max(0, start - SNIPPET_RADIUS), min(len(body), start + SNIPPET_RADIUS)
    text = " ".join(body[lo:hi].split())
    return ("…" if lo > 0 else "") + text + ("…" if hi < len(body) else "")


def _score(doc: _Doc, terms: list[str]) -> int | None:
    title, meta, body = fold(doc.title), fold(" ".join([doc.summary, *doc.tags])), fold(doc.body)
    score = 0
    for t in terms:
        if t in title:
            score += TITLE_WEIGHT
        elif t in meta:
            score += META_WEIGHT
        elif t in body:
            score += BODY_WEIGHT * min(body.count(t), BODY_CAP)
        else:
            return None  # every term must match somewhere
    return score


def search(vault: Vault, query: str, page_type: str | None = None, limit: int = 20, raw: bool = False) -> dict:
    terms = fold(query).split()
    if not terms:
        raise WikiError("empty_query", "Search query must contain at least one term.")
    if limit < 1:
        raise WikiError("invalid_limit", "--limit must be at least 1.")
    if raw and page_type:
        raise WikiError("invalid_option", "--type cannot be combined with --raw.")
    if raw:
        raws = iter_raw(vault)
        docs = [_Doc(r.rel, r.title, "raw", "", [], r.body) for r in raws]
        links = {r.rel: f"[[{r.stem}]]" for r in raws}
    else:
        pages = [p for p in iter_pages(vault) if page_type is None or p.folder_type == page_type]
        docs = [_Doc(p.rel, p.stem, p.folder_type or p.type or "unknown", p.summary, p.tags, p.body) for p in pages]
        links = {p.rel: p.link for p in pages}
    scored = [(s, d) for d in docs if (s := _score(d, terms)) is not None]
    scored.sort(key=lambda sd: (-sd[0], key(sd[1].title), sd[1].path))
    results = [
        {
            "path": d.path,
            "title": d.title,
            "type": d.type,
            "summary": d.summary,
            "link": links[d.path],
            "score": s,
            "snippet": _snippet(d.body, terms),
        }
        for s, d in scored[:limit]
    ]
    return {"query": query, "total": len(scored), "results": results}
