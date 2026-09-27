"""Obsidian-compatible wikilink parsing and resolution."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .naming import EXT, key, nfc
from .pages import Page
from .vault import Vault

_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")
_BLANK = re.compile(r"[^\n]")


@dataclass(frozen=True)
class Link:
    raw: str  # the full `[[...]]` text
    target: str  # page name or vault path, without anchor/alias ('' = same page)
    anchor: str | None  # heading or ^block
    alias: str | None
    embed: bool


def mask_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans, preserving offsets."""
    out, fence = [], None
    for line in text.splitlines(keepends=True):
        m = _FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)[0] * 3
        elif fence is not None and m and m.group(1).startswith(fence):
            fence = None
        elif fence is None:
            out.append(_INLINE_CODE.sub(lambda mm: " " * len(mm.group(0)), line))
            continue
        out.append(_BLANK.sub(" ", line))  # fence line or inside a fence
    return "".join(out)


def parse_link(raw: str, inner: str, embed: bool = False) -> Link:
    target, _, alias = inner.partition("|")
    name, _, anchor = target.partition("#")
    return Link(
        raw=raw,
        target=name.strip(),
        anchor=anchor.strip() or None,
        alias=alias.strip() or None,
        embed=embed,
    )


def extract_links(text: str) -> list[Link]:
    return [parse_link(m.group(0), m.group(2), bool(m.group(1))) for m in _WIKILINK.finditer(mask_code(text))]


def links_in_meta(meta: object) -> list[Link]:
    """Wikilinks inside frontmatter values (Obsidian treats these as links too)."""
    out: list[Link] = []

    def walk(v: object) -> None:
        if isinstance(v, str):
            out.extend(parse_link(m.group(0), m.group(2), bool(m.group(1))) for m in _WIKILINK.finditer(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(meta)
    return out


def page_links(page: Page) -> list[Link]:
    return links_in_meta(page.meta or {}) + extract_links(page.body)


def _vault_files(vault: Vault) -> Iterator[str]:
    """Vault-relative NFC paths of all non-hidden files."""
    for dirpath, dirnames, filenames in os.walk(vault.root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        base = Path(dirpath)
        for f in sorted(filenames):
            if not f.startswith("."):
                yield nfc((base / f).relative_to(vault.root).as_posix())


def _file_key(rel_or_name: str) -> str:
    """md files are addressed without extension; attachments with it."""
    s = nfc(rel_or_name)
    return key(s) if s.lower().endswith(EXT) else s.casefold()


class Resolver:
    """Resolves link targets to vault-relative paths the way Obsidian would for this vault."""

    def __init__(self, vault: Vault, pages: Iterable[Page]) -> None:
        self.pages_by_name: dict[str, list[str]] = {}
        for p in pages:
            self.pages_by_name.setdefault(key(p.stem), []).append(p.rel)
        self.files_by_name: dict[str, list[str]] = {}
        self.files_by_path: dict[str, str] = {}
        for rel in _vault_files(vault):
            self.files_by_name.setdefault(_file_key(rel.rsplit("/", 1)[-1]), []).append(rel)
            self.files_by_path[_file_key(rel)] = rel

    def resolve(self, target: str) -> str | None:
        """Vault-relative path for `target`, '' for a same-page link, None if unresolved."""
        t = nfc(target).strip()
        if not t:
            return ""
        if "/" in t:
            k = _file_key(t.strip("/"))
            if k in self.files_by_path:
                return self.files_by_path[k]
            matches = sorted(rel for pk, rel in self.files_by_path.items() if pk.endswith("/" + k))
            return matches[0] if matches else None
        k = _file_key(t)
        hits = self.pages_by_name.get(k) or self.files_by_name.get(k)
        return hits[0] if hits else None
