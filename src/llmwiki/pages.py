"""Frontmatter parsing/writing and the wiki page model."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import WikiError
from .naming import EXT, key, nfc, title_to_stem
from .vault import DIR_TYPES, PAGE_TYPES, Vault

_FM = re.compile(r"\A---[ \t]*\n(.*?\n)?---[ \t]*(?:\n|\Z)", re.S)

PAGE_FIELDS = ("type", "summary", "sources", "tags", "created", "updated")


class _Dumper(yaml.SafeDumper):
    """SafeDumper that never emits &anchors/*aliases (e.g. for a shared date object)."""

    def ignore_aliases(self, data: object) -> bool:
        return True


@dataclass
class Doc:
    meta: dict | None
    body: str
    error: str | None  # None, "missing", or a description of why it is invalid


def parse(text: str) -> Doc:
    """Split a markdown document into frontmatter and body."""
    text = text.replace("\r\n", "\n")
    m = _FM.match(text)
    if not m:
        return Doc(None, text, "missing")
    body = text[m.end():]
    if body.startswith("\n"):  # the conventional blank line after the closing ---
        body = body[1:]
    try:
        meta = yaml.safe_load(m.group(1) or "")
    except yaml.YAMLError as e:
        return Doc(None, body, f"unparseable YAML: {e}".replace("\n", " "))
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        return Doc(None, body, "frontmatter is not a mapping")
    return Doc(meta, body, None)


def dump(meta: dict, body: str = "") -> str:
    """Serialise frontmatter (keys in the given order) followed by the body."""
    y = yaml.dump(meta, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=10_000)
    body = body.lstrip("\n")
    return f"---\n{y}---\n" + (f"\n{body}" if body else "")


def iter_md(directory: Path) -> Iterator[Path]:
    """Markdown files under `directory`, skipping hidden files/dirs, in stable order."""
    if not directory.is_dir():
        return iter(())
    found = [
        p
        for p in directory.rglob(f"*{EXT}")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(directory).parts)
    ]
    return iter(sorted(found, key=lambda p: nfc(p.relative_to(directory).as_posix())))


@dataclass
class Page:
    path: Path
    rel: str  # vault-relative, NFC
    stem: str  # NFC title (the filename without .md)
    fs_stem: str  # the stem exactly as stored on disk
    folder_type: str | None  # type implied by the folder, None if outside a type folder
    meta: dict | None
    body: str
    fm_error: str | None

    @property
    def title(self) -> str:
        return self.stem

    @property
    def type(self) -> str | None:
        t = (self.meta or {}).get("type")
        return t if isinstance(t, str) else None

    @property
    def summary(self) -> str:
        s = (self.meta or {}).get("summary")
        return " ".join(str(s).split()) if s else ""

    @property
    def tags(self) -> list[str]:
        t = (self.meta or {}).get("tags")
        return [str(x) for x in t] if isinstance(t, list) else []

    @property
    def link(self) -> str:
        return f"[[{self.stem}]]"

    def problems(self) -> list[str]:
        """Frontmatter contract violations (empty if valid or if frontmatter is missing)."""
        if self.meta is None:
            return [self.fm_error] if self.fm_error and self.fm_error != "missing" else []
        m = self.meta
        out = [f"missing field `{f}`" for f in PAGE_FIELDS if f not in m]
        if "type" in m and m["type"] not in PAGE_TYPES:
            out.append(f"`type` must be one of {', '.join(PAGE_TYPES)}")
        if "summary" in m and not (m["summary"] is None or isinstance(m["summary"], str)):
            out.append("`summary` must be a string")
        for f in ("sources", "tags", "authors"):
            if f in m and not isinstance(m[f], list):
                out.append(f"`{f}` must be a list")
        for f in ("created", "updated"):
            if f in m and not isinstance(m[f], (dt.date, str)):
                out.append(f"`{f}` must be a date")
        if m.get("type") == "source" and not (isinstance(m.get("raw"), str) and m["raw"].strip()):
            out.append("source pages need a `raw` field pointing at a file under raw/")
        return out


def load_page(vault: Vault, path: Path) -> Page:
    rel_parts = path.relative_to(vault.wiki_dir).parts
    folder_type = DIR_TYPES.get(nfc(rel_parts[0])) if len(rel_parts) > 1 else None
    doc = parse(path.read_text(encoding="utf-8"))
    fs_stem = path.name[: -len(EXT)]
    return Page(
        path=path,
        rel=nfc(path.relative_to(vault.root).as_posix()),
        stem=nfc(fs_stem),
        fs_stem=fs_stem,
        folder_type=folder_type,
        meta=doc.meta,
        body=doc.body,
        fm_error=doc.error,
    )


def iter_pages(vault: Vault) -> list[Page]:
    return [load_page(vault, p) for p in iter_md(vault.wiki_dir)]


def new_page_meta(page_type: str, today: dt.date, raw: str | None = None) -> dict:
    meta: dict = {
        "type": page_type,
        "summary": "",
        "sources": [],
        "tags": [],
        "created": today,
        "updated": today,
    }
    if raw is not None:
        meta["raw"] = raw
    return meta


def resolve_raw_arg(vault: Vault, raw: str | Path) -> str:
    """Validate a `--raw` argument; return it as a vault-relative `raw/...` path."""
    p = Path(raw).expanduser()
    candidates = [p] if p.is_absolute() else [vault.root / p, Path.cwd() / p]
    for c in candidates:
        c = c.resolve()
        if c.is_file():
            break
    else:
        raise WikiError("invalid_raw", f"--raw {raw}: no such file.")
    try:
        inner = c.relative_to(vault.raw_dir.resolve())
    except ValueError:
        raise WikiError("invalid_raw", f"--raw {raw}: must be a file under {vault.rel(vault.raw_dir)}/.") from None
    if inner.parts[0].startswith(".") or c.suffix != EXT:
        raise WikiError("invalid_raw", f"--raw {raw}: must be a captured .md source under raw/ (not raw/.orig).")
    return nfc(vault.rel(c))


def create_page(
    vault: Vault,
    page_type: str,
    title: str,
    raw: str | Path | None = None,
    today: dt.date | None = None,
) -> dict:
    """Create a new page named after `title`; refuse duplicates vault-wide."""
    if page_type not in PAGE_TYPES:
        raise WikiError("invalid_type", f"--type must be one of {', '.join(PAGE_TYPES)}.")
    if page_type == "source" and raw is None:
        raise WikiError("invalid_raw", "Source pages require --raw <path of the captured raw file>.")
    if page_type != "source" and raw is not None:
        raise WikiError("invalid_raw", "--raw is only valid with --type source.")
    stem = title_to_stem(title)
    raw_rel = resolve_raw_arg(vault, raw) if raw is not None else None
    k = key(stem)
    for existing in iter_pages(vault):
        if key(existing.stem) == k:
            raise WikiError(
                "duplicate_title",
                f"A page named {existing.stem!r} already exists at {existing.rel}. "
                f"Link to it, or choose a disambiguated title such as '{stem} ({page_type})'.",
                existing=existing.rel,
            )
    path = vault.type_dir(page_type) / f"{stem}{EXT}"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = new_page_meta(page_type, today or dt.date.today(), raw_rel)
    with path.open("x", encoding="utf-8") as f:
        f.write(dump(meta, f"# {stem}\n"))
    return {"path": vault.rel(path), "title": stem, "type": page_type, "link": f"[[{stem}]]", "raw": raw_rel}
