"""Title -> filename rules and the uniqueness key for page names.

The page title *is* the filename stem, so Obsidian `[[wikilinks]]` read
naturally. Everything that makes that safe lives here.
"""

from __future__ import annotations

import re
import unicodedata

from .errors import WikiError

MAX_FILENAME_BYTES = 200
EXT = ".md"

# Illegal on macOS/Linux/Windows, plus characters that break Obsidian wikilinks.
_REPLACED = set('/\\:*?"<>|') | set("#^[]")
_EDGES = re.compile(r"^[\s.]+|[\s.]+$")
_SPACES = re.compile(r"\s+")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def sanitize(title: str, max_bytes: int) -> str:
    """Return a safe filename stem of at most `max_bytes` UTF-8 bytes ('' if nothing usable)."""
    s = nfc(title)
    s = "".join(" " if (c in _REPLACED or unicodedata.category(c) == "Cc") else c for c in s)
    s = _SPACES.sub(" ", s)
    s = _EDGES.sub("", s)
    if len(s.encode("utf-8")) > max_bytes:
        out, used = [], 0
        for c in s:
            n = len(c.encode("utf-8"))
            if used + n > max_bytes:
                break
            out.append(c)
            used += n
        s = _EDGES.sub("", "".join(out))
    return s


def title_to_stem(title: str) -> str:
    stem = sanitize(title, MAX_FILENAME_BYTES - len(EXT))
    if not stem:
        raise WikiError("empty_title", f"Title {title!r} has no usable characters for a filename.")
    return stem


def title_to_filename(title: str) -> str:
    return title_to_stem(title) + EXT


def is_canonical_stem(stem: str) -> bool:
    """True if `stem` is exactly what the naming rules would produce for itself."""
    try:
        return title_to_stem(stem) == stem and unicodedata.is_normalized("NFC", stem)
    except WikiError:
        return False


def key(name: str) -> str:
    """Uniqueness/lookup key: NFC, case-folded, without a trailing .md."""
    s = nfc(name)
    if s.lower().endswith(EXT):
        s = s[: -len(EXT)]
    return s.casefold()
