"""Term search over wiki pages (or raw sources), aware of word forms.

Each query term matches a field in one of three tiers: exact word (after
folding) > same lemma/stem > substring. Fields rank title > summary/tags >
body; see design D4 of the search-morphology change for the scoring.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .errors import WikiError
from .fetch import clean_authors
from .morph import Analyzer, Token, fold, fold_with_map, query_words, tokenize
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


def _author_tier(names: list[str], words: list[str], an: Analyzer, exact_only: bool) -> str | None:
    """Tier at which every query word matches a word of one author name (None if no name matches).

    Names are matched on lemmas *plus* each word's own folded form: pymorphy3 may read an unknown
    surname in -ов/-ин as a plural noun (Синтетов -> синтет), while its declined form lemmatises
    back to the nominative (Синтетова -> синтетов), which then equals the stored name's folded form.
    """
    for name in names:
        toks = [t.text for t in tokenize(name, compounds=False)]
        folded = [fold(t) for t in toks]
        keys = [an.keys(t) | {f} for t, f in zip(toks, folded)]
        tiers = []
        for w in words:
            wf = fold(w)
            wk = an.keys(w) | {wf}
            if wf in folded:
                tiers.append("exact")
            elif not exact_only and any(wk & k for k in keys):
                tiers.append("lemma")
            else:
                break
        else:
            return max(tiers, key=TIERS.index) if tiers else None
    return None


def _author_names(meta: dict | None) -> list[str]:
    a = (meta or {}).get("authors")
    return clean_authors(a) if isinstance(a, list) else []


def search(
    vault: Vault,
    query: str,
    page_type: str | None = None,
    limit: int = 20,
    raw: bool = False,
    exact: bool = False,
    author: str | None = None,
) -> tuple[dict, list[str]]:
    """Returns (result document, warnings)."""
    words = query_words(unicodedata.normalize("NFC", query))
    author_words = [t.text for t in tokenize(unicodedata.normalize("NFC", author or ""), compounds=False)]
    if author is not None and not author_words:
        raise WikiError("empty_query", "--author must contain at least one word.")
    if not words and not author_words:
        raise WikiError("empty_query", "Search query must contain at least one word (or use --author).")
    if limit < 1:
        raise WikiError("invalid_limit", "--limit must be at least 1.")
    if raw and page_type:
        raise WikiError("invalid_option", "--type cannot be combined with --raw.")

    cache = LemmaCache(vault)
    an = Analyzer(cache.load())
    terms = list({fold(w): _Term(fold(w), an.keys(w)) for w in words}.values())

    def doc(path: str, title: str, type_: str, summary: str, tags: list[str], body: str, link: str,
            aliases: list[str] = ()) -> _Doc:
        title_text = " · ".join([title, *aliases])  # aliases rank as title matches
        fields = {"title": _field(title_text, an), "meta": _field(" ".join([summary, *tags]), an),
                  "body": _field(body, an)}
        return _Doc(path, title, type_, summary, link, fields)

    all_pages = iter_pages(vault) if (not raw or author_words) else []
    aliases_by_key = {key(p.stem): p.aliases for p in all_pages if p.aliases}
    if raw:
        entries = [(r.meta, lambda r=r: doc(r.rel, r.title, "raw", "", [], r.body, f"[[{r.stem}]]"))
                   for r in iter_raw(vault)]
    else:
        entries = [
            (p.meta, lambda p=p: doc(p.rel, p.stem, p.folder_type or p.type or "unknown", p.summary, p.tags, p.body,
                                     p.link, p.aliases))
            for p in all_pages
            if page_type is None or p.folder_type == page_type
        ]

    candidates: list[tuple[_Doc, str | None]] = []
    for meta, make in entries:
        a_tier = None
        if author_words:
            names = _author_names(meta)
            names += [alias for n in names for alias in aliases_by_key.get(key(n), [])]  # person-page aliases
            a_tier = _author_tier(names, author_words, an, exact)
            if a_tier is None:
                continue
        candidates.append((make(), a_tier))

    if terms:
        scored = [(ev, d) for d, _ in candidates if (ev := _evaluate(d, terms, exact)) is not None]
        scored.sort(key=lambda x: (-x[0][0], -x[0][1], key(x[1].title), x[1].path))
    else:  # --author only: everything by that author, by title
        scored = sorted((((0, 0, a_tier), d) for d, a_tier in candidates), key=lambda x: (key(x[1].title), x[1].path))
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
    out = {"query": query, "exact": exact, "total": len(scored), "results": results}
    if author is not None:
        out["author"] = author
    return out, cache.warnings
