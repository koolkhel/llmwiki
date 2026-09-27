"""Word forms for search: folding, tokenizing, and lemma/stem keys.

- Russian words map to *all* their dictionary forms (pymorphy3), so `кошек`
  and `кошкой` share the key `кошка`, and `бегу` yields {бег, бежать}.
- English words map to their Snowball (Porter2) stem.
- Anything else maps to its folded form.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

FOLD_VERSION = 1

# A word: letters/digits. Text containing combining marks (e.g. Russian stress
# marks, which never compose in NFC) uses slower patterns that keep them inside words.
_MARKS = re.compile(r"[\u0300-\u036f]")
_WORD = re.compile(r"[^\W_]+")
_COMPOUND = re.compile(r"[^\W_]+(?:-[^\W_]+)+")
_WORD_M = re.compile(r"(?:[^\W_][\u0300-\u036f]*)+")
_COMPOUND_M = re.compile(r"(?:[^\W_][\u0300-\u036f]*)+(?:-(?:[^\W_][\u0300-\u036f]*)+)+")


def _is_cyrillic(ch: str) -> bool:
    return "\u0400" <= ch <= "\u04ff"


# ASCII and Cyrillic (U+0400-U+04FF, minus ё/Ё) case-fold one-to-one and need no
# decomposition, so runs of them take a fast path; everything else goes char by char.
_SIMPLE_RUN = re.compile(r"[\x00-\x7f\u0400-\u0400\u0402-\u044f\u0452-\u04ff]+")


def _fold_char(ch: str) -> str:
    if ch in "ёЁ":
        return "е"
    if _is_cyrillic(ch):
        return ch.casefold()  # no decomposition: keeps й distinct from и
    return "".join(d.casefold() for d in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(d))


def fold_with_map(s: str) -> tuple[str, list[int]]:
    """Case-folded text without Latin diacritics, `ё`->`е`, `й` kept; plus folded->source index map.

    Indexes refer to positions in `s` as given (callers pass NFC text).
    """
    out: list[str] = []
    idx: list[int] = []
    pos = 0
    for m in _SIMPLE_RUN.finditer(s):
        for i in range(pos, m.start()):
            pieces = _fold_char(s[i])
            out.append(pieces)
            idx.extend([i] * len(pieces))
        out.append(m.group(0).casefold())
        idx.extend(range(m.start(), m.end()))
        pos = m.end()
    for i in range(pos, len(s)):
        pieces = _fold_char(s[i])
        out.append(pieces)
        idx.extend([i] * len(pieces))
    return "".join(out), idx


@lru_cache(maxsize=200_000)
def fold(s: str) -> str:
    return fold_with_map(unicodedata.normalize("NFC", s))[0]


@dataclass(frozen=True)
class Token:
    text: str  # as in the source text
    start: int
    end: int


def tokenize(text: str, compounds: bool = True) -> list[Token]:
    """Words of `text` with offsets. Hyphenated compounds are also emitted joined (`нейро-сеть` -> `нейросеть`)."""
    word, compound = (_WORD_M, _COMPOUND_M) if _MARKS.search(text) else (_WORD, _COMPOUND)
    tokens = [Token(m.group(0), m.start(), m.end()) for m in word.finditer(text)]
    if compounds and "-" in text:
        tokens += [Token(m.group(0).replace("-", ""), m.start(), m.end()) for m in compound.finditer(text)]
        tokens.sort(key=lambda t: (t.start, -t.end))
    return tokens


def versions() -> str:
    """Identifies everything that affects keys(); used to invalidate caches."""
    from importlib.metadata import PackageNotFoundError, version

    parts = [f"fold{FOLD_VERSION}"]
    for pkg in ("pymorphy3", "pymorphy3-dicts-ru", "snowballstemmer"):
        try:
            parts.append(f"{pkg}={version(pkg)}")
        except PackageNotFoundError:
            parts.append(f"{pkg}=none")
    return "|".join(parts)


class Analyzer:
    """Computes (and memoizes) the lemma/stem keys of words.

    `memo` maps folded word -> keys, e.g. preloaded from the search cache;
    forms computed during this run are collected in `new` for write-back.
    """

    def __init__(self, memo: dict[str, frozenset[str]] | None = None) -> None:
        self.memo: dict[str, frozenset[str]] = dict(memo or {})
        self.new: dict[str, frozenset[str]] = {}
        self._morph = None
        self._stemmer = None

    def _lemmas(self, word: str) -> frozenset[str]:
        if self._morph is None:
            import pymorphy3

            self._morph = pymorphy3.MorphAnalyzer()
        return frozenset(fold(p.normal_form) for p in self._morph.parse(word)) or frozenset({word})

    def _stem(self, word: str) -> frozenset[str]:
        if self._stemmer is None:
            import snowballstemmer

            self._stemmer = snowballstemmer.stemmer("english")
        return frozenset({self._stemmer.stemWord(word)})

    def keys(self, word: str) -> frozenset[str]:
        f = fold(word)
        hit = self.memo.get(f)
        if hit is not None:
            return hit
        if f and all(_is_cyrillic(c) for c in f):
            k = self._lemmas(f)
        elif f.isascii() and f.isalpha():
            k = self._stem(f)
        else:
            k = frozenset({f})
        self.memo[f] = k
        self.new[f] = k
        return k
