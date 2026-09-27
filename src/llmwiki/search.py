"""Term search over wiki pages (or raw sources), aware of word forms.

Each query term matches a field in one of three tiers: exact word (after
folding) > same lemma/stem > substring. Fields rank title > summary/tags >
body; see design D4 of the search-morphology change for the scoring.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .errors import WikiError
from .morph import Analyzer, Token, fold, fold_with_map, tokenize
from .naming import key
from .pages import iter_pages
from .searchcache import LemmaCache
from .sources import iter_raw
from .vault import Vault

SNIPPET_RADIUS = 80
FIELD_WEIGHTS = {"title": 100, "meta": 10, "body": 1}
TIER_WEIGHTS = {"exact": 3, "lemma": 2, "substring": 1}
TIERS = ("exact", "lemma", "substring")  # strongest first


@dataclass
class _Field:
    text: str  # NFC
    folded: str
    fmap: list[int]
    tokens: list[Token]
    tfolded: list[str]
    tkeys: list[frozenset[str]]
    exact: set[str]
    keys: set[str]


def _field(text: str, an: Analyzer) -> _Field:
    text = unicodedata.normalize("NFC", text)
    folded, fmap = fold_with_map(text)
    tokens = tokenize(text)
    tfolded = [fold(t.text) for t in tokens]
    tkeys = [an.keys(t.text) for t in tokens]
    return _Field(text, folded, fmap, tokens, tfolded, tkeys, set(tfolded), set().union(*tkeys))


@dataclass
class _Doc:
    path: str
    title: str
    type: str
    summary: str
    link: str
    fields: dict[str, _Field]


@dataclass(frozen=True)
class _Term:
    folded: str
    keys: frozenset[str]


def _tier(f: _Field, t: _Term, exact_only: bool) -> str | None:
    if t.folded in f.exact:
        return "exact"
    if exact_only:
        return None
    if t.keys & f.keys:
        return "lemma"
    if t.folded in f.folded:
        return "substring"
    return None


def _token_hits(f: _Field, t: _Term, exact_only: bool) -> list[int]:
    """Indexes of tokens in `f` that match `t` as a word (exact or lemma)."""
    return [
        i
        for i, (tf, tk) in enumerate(zip(f.tfolded, f.tkeys))
        if tf == t.folded or (not exact_only and t.keys & tk)
    ]


def _snippet(f: _Field, terms: list[_Term], exact_only: bool) -> str:
    starts = [f.tokens[h[0]].start for t in terms if (h := _token_hits(f, t, exact_only))]
    if not starts and not exact_only:
        starts = [f.fmap[p] for t in terms if (p := f.folded.find(t.folded)) >= 0]
    body = f.text
    if not starts:
        return " ".join(body.split())[: 2 * SNIPPET_RADIUS]
    start = min(starts)
    lo, hi = max(0, start - SNIPPET_RADIUS), min(len(body), start + SNIPPET_RADIUS)
    text = " ".join(body[lo:hi].split())
    return ("…" if lo > 0 else "") + text + ("…" if hi < len(body) else "")


def _evaluate(doc: _Doc, terms: list[_Term], exact_only: bool) -> tuple[int, int, str] | None:
    """(score, body hit count, match tier) or None if some term does not match."""
    score, needed = 0, []
    for t in terms:
        best_value, best_tier = 0, None
        for name, f in doc.fields.items():
            tier = _tier(f, t, exact_only)
            if tier is None:
                continue
            value = FIELD_WEIGHTS[name] * TIER_WEIGHTS[tier]
            best_value = max(best_value, value)
            if best_tier is None or TIERS.index(tier) < TIERS.index(best_tier):
                best_tier = tier
        if best_tier is None:
            return None
        score += best_value
        needed.append(best_tier)
    body = doc.fields["body"]
    hits = sum(len(_token_hits(body, t, exact_only)) or body.folded.count(t.folded) for t in terms)
    return score, hits, max(needed, key=TIERS.index)


def search(
    vault: Vault,
    query: str,
    page_type: str | None = None,
    limit: int = 20,
    raw: bool = False,
    exact: bool = False,
) -> tuple[dict, list[str]]:
    """Returns (result document, warnings)."""
    words = [t.text for t in tokenize(unicodedata.normalize("NFC", query), compounds=False)]
    if not words:
        raise WikiError("empty_query", "Search query must contain at least one word.")
    if limit < 1:
        raise WikiError("invalid_limit", "--limit must be at least 1.")
    if raw and page_type:
        raise WikiError("invalid_option", "--type cannot be combined with --raw.")

    cache = LemmaCache(vault)
    an = Analyzer(cache.load())
    terms = list({fold(w): _Term(fold(w), an.keys(w)) for w in words}.values())

    def doc(path: str, title: str, type_: str, summary: str, tags: list[str], body: str, link: str) -> _Doc:
        fields = {"title": _field(title, an), "meta": _field(" ".join([summary, *tags]), an), "body": _field(body, an)}
        return _Doc(path, title, type_, summary, link, fields)

    if raw:
        docs = [doc(r.rel, r.title, "raw", "", [], r.body, f"[[{r.stem}]]") for r in iter_raw(vault)]
    else:
        docs = [
            doc(p.rel, p.stem, p.folder_type or p.type or "unknown", p.summary, p.tags, p.body, p.link)
            for p in iter_pages(vault)
            if page_type is None or p.folder_type == page_type
        ]

    scored = [(ev, d) for d in docs if (ev := _evaluate(d, terms, exact)) is not None]
    scored.sort(key=lambda x: (-x[0][0], -x[0][1], key(x[1].title), x[1].path))
    results = [
        {
            "path": d.path,
            "title": d.title,
            "type": d.type,
            "summary": d.summary,
            "link": d.link,
            "match": match,
            "score": score,
            "snippet": _snippet(d.fields["body"], terms, exact),
        }
        for (score, _hits, match), d in scored[:limit]
    ]
    cache.save(an.new)
    return {"query": query, "exact": exact, "total": len(scored), "results": results}, cache.warnings
