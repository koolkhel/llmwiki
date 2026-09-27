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

FOLD_VERSION = 2  # 2: keep non-Latin combining marks (Indic etc.) instead of dropping them

# A word: letters/digits, plus any combining marks inside it (Russian stress marks,
# Devanagari vowel signs / virama / nukta, ...). Text without marks uses the fast
# patterns; the full mark class is built lazily (~10 ms) the first time it is needed.
_WORD = re.compile(r"[^\W_]+")
_COMPOUND = re.compile(r"[^\W_]+(?:-[^\W_]+)+")
# Quick pre-check: only text with characters outside ASCII+Cyrillic can contain marks or Han.
_MAYBE_MARKS = re.compile(r"[^\x00-\x7f\u0400-\u04ff]")
# Han ideographs (CJK Unified + Extension A, Compatibility, Extensions B+).
_HAN_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003ffff]{2,}")
# Diacritics that folding removes: the Combining Diacritical Marks blocks (Latin/Greek/Cyrillic).
_DIACRITIC_RANGES = ((0x0300, 0x036F), (0x1AB0, 0x1AFF), (0x1DC0, 0x1DFF), (0x20D0, 0x20FF), (0xFE20, 0xFE2F))


def _is_diacritic(ch: str) -> bool:
    cp = ord(ch)
    return any(a <= cp <= b for a, b in _DIACRITIC_RANGES)


@lru_cache(maxsize=1)
def _mark_patterns() -> tuple[re.Pattern, re.Pattern, re.Pattern]:
    ranges: list[tuple[int, int]] = []
    start = prev = None
    for cp in range(0x10000):
        if unicodedata.category(chr(cp)) in ("Mn", "Mc", "Me"):
            if start is None:
                start = cp
            prev = cp
        elif start is not None:
            ranges.append((start, prev))
            start = None
    marks = "".join(rf"\u{a:04x}-\u{b:04x}" if a != b else rf"\u{a:04x}" for a, b in ranges)
    word = rf"[^\W_](?:[^\W_]|[{marks}])*"
    return (re.compile(f"[{marks}]"), re.compile(word), re.compile(rf"{word}(?:-{word})+"))


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
    return "".join(d.casefold() for d in unicodedata.normalize("NFKD", ch) if not _is_diacritic(d))


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


def tokenize(text: str, compounds: bool = True, cjk: bool = True) -> list[Token]:
    """Words of `text` with offsets.

    Hyphenated compounds are also emitted joined (`нейро-сеть` -> `нейросеть`), and runs of
    two or more Han ideographs are also emitted as their overlapping two-character pieces.
    """
    word, compound = _WORD, _COMPOUND
    # Marks and Han ideographs only occur outside ASCII+Cyrillic: one fast check gates both.
    exotic = _MAYBE_MARKS.search(text) is not None
    if exotic:
        marks, word_m, compound_m = _mark_patterns()
        if marks.search(text):
            word, compound = word_m, compound_m
    tokens = [Token(m.group(0), m.start(), m.end()) for m in word.finditer(text)]
    extra = False
    if compounds and "-" in text:
        tokens += [Token(m.group(0).replace("-", ""), m.start(), m.end()) for m in compound.finditer(text)]
        extra = True
    if cjk and exotic:
        for m in _HAN_RUN.finditer(text):
            s, run = m.start(), m.group(0)
            tokens += [Token(run[i:i + 2], s + i, s + i + 2) for i in range(len(run) - 1)]
            extra = True
    if extra:
        tokens.sort(key=lambda t: (t.start, -t.end))
    return tokens


def query_words(text: str) -> list[str]:
    """Query terms: words, with an all-Han word of 2+ characters replaced by its two-character pieces."""
    out: list[str] = []
    for t in tokenize(text, compounds=False, cjk=False):
        if len(t.text) >= 2 and _HAN_RUN.fullmatch(t.text):
            out += [t.text[i:i + 2] for i in range(len(t.text) - 1)]
        else:
            out.append(t.text)
    return out


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
