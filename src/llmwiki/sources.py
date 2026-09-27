"""Capturing raw sources (URLs and text files) into immutable raw/ files."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from . import fetch as fetch_mod
from .errors import WikiError
from .naming import EXT, MAX_FILENAME_BYTES, nfc, sanitize
from .pages import Page, dump, iter_md, iter_pages, parse, resolve_raw_arg
from .vault import Vault

_URL = re.compile(r"^https?://", re.I)
_HEADING = re.compile(r"^#[ \t]+(.+?)[ \t#]*$", re.M)
FILE_SUFFIXES = (".txt", ".md")
HTML_SUFFIXES = (".html", ".htm")
HASH_SUFFIX_LEN = 8
_DATE_PREFIX_LEN = len("YYYY-MM-DD-")
_RAW_TITLE_BYTES = MAX_FILENAME_BYTES - len(EXT) - _DATE_PREFIX_LEN - (1 + HASH_SUFFIX_LEN)


def normalize_text(text: str) -> str:
    """The canonical form of a body for hashing and storage."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


@dataclass
class RawSource:
    path: Path
    rel: str
    stem: str
    meta: dict | None
    body: str
    fm_error: str | None

    @property
    def title(self) -> str:
        t = (self.meta or {}).get("title")
        return str(t) if t else self.stem

    @property
    def sha256(self) -> str | None:
        s = (self.meta or {}).get("sha256")
        return str(s) if s else None


def iter_raw(vault: Vault) -> list[RawSource]:
    out = []
    for p in iter_md(vault.raw_dir):  # hidden dirs (raw/.orig) are skipped
        doc = parse(p.read_text(encoding="utf-8"))
        out.append(RawSource(p, nfc(vault.rel(p)), nfc(p.name[: -len(EXT)]), doc.meta, doc.body, doc.error))
    return out


def raw_path_for(vault: Vault, date: dt.date, title: str, sha: str) -> Path:
    stem = f"{date.isoformat()}-{sanitize(title, _RAW_TITLE_BYTES) or 'untitled'}"
    path = vault.raw_dir / f"{stem}{EXT}"
    if path.exists():
        path = vault.raw_dir / f"{stem}-{sha[:HASH_SUFFIX_LEN]}{EXT}"
    n = 2
    while path.exists():  # same title, same day, same hash prefix: vanishingly rare
        path = vault.raw_dir / f"{stem}-{sha[:HASH_SUFFIX_LEN]}-{n}{EXT}"
        n += 1
    return path


def find_duplicate(raws: list[RawSource], sha: str, normalized_url: str | None = None) -> RawSource | None:
    for r in raws:
        m = r.meta or {}
        if m.get("sha256") == sha:
            return r
        if normalized_url and m.get("kind") == "url" and m.get("normalized_url") == normalized_url:
            return r
    return None


def _norm_ref(ref: str) -> str:
    ref = nfc(ref.strip())
    return ref[2:] if ref.startswith("./") else ref


def ingested_by(pages: list[Page]) -> dict[str, list[str]]:
    """raw rel path -> source pages declaring it in their `raw` field."""
    out: dict[str, list[str]] = {}
    for p in pages:
        raw = (p.meta or {}).get("raw")
        if p.folder_type == "source" and isinstance(raw, str) and raw.strip():
            out.setdefault(_norm_ref(raw), []).append(p.rel)
    return out


def source_status(vault: Vault, raw_rel: str, pages: list[Page] | None = None) -> str:
    pages = iter_pages(vault) if pages is None else pages
    return "ingested" if raw_rel in ingested_by(pages) else "pending"


def _write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        f.write(text)


def _result(vault: Vault, raw: RawSource | None, path: Path | None, meta: dict, duplicate: bool) -> dict:
    rel = raw.rel if raw else nfc(vault.rel(path))
    m = raw.meta if raw else meta
    return {
        "path": rel,
        "title": (raw.title if raw else meta["title"]),
        "kind": (m or {}).get("kind"),
        "sha256": (m or {}).get("sha256"),
        "status": source_status(vault, rel),
        "created": not duplicate,
        "duplicate_of": rel if duplicate else None,
    }


def _now(now: dt.datetime | None) -> dt.datetime:
    return (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).replace(microsecond=0)


def _stamp(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def capture_url(vault: Vault, url: str, now: dt.datetime | None = None) -> dict:
    page = fetch_mod.fetch(url)
    body = normalize_text(page.body)
    sha = content_hash(body)
    dup = find_duplicate(iter_raw(vault), sha, page.normalized_url)
    if dup:
        return _result(vault, dup, None, {}, duplicate=True)
    now = _now(now)
    path = raw_path_for(vault, now.astimezone().date(), page.title, sha)
    orig = vault.orig_dir / f"{path.name[: -len(EXT)]}.html"
    meta: dict = {
        "kind": "url",
        "title": page.title,
        "authors": page.authors or None,
        "original_url": page.original_url,
        "canonical_url": page.canonical_url,
        "normalized_url": page.normalized_url,
        "captured_at": _stamp(now),
        "published": page.published,
        "language": page.language,
        "extractor": page.extractor,
        "sha256": sha,
        "original_file": nfc(orig.relative_to(vault.root).as_posix()),
    }
    meta = {k: v for k, v in meta.items() if v is not None}
    orig.parent.mkdir(parents=True, exist_ok=True)
    with orig.open("xb") as f:
        f.write(page.html_bytes)
    _write_new(path, dump(meta, body + "\n"))
    return _result(vault, None, path, meta, duplicate=False)


def _file_title(meta: dict | None, body: str, fallback: str) -> str:
    t = (meta or {}).get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    m = _HEADING.search(body)
    return m.group(1).strip() if m else fallback


def _source_file(vault: Vault, arg: str) -> Path:
    """Resolve and validate a local source path (existence, type, suffix, not already in raw/)."""
    p = Path(arg).expanduser()
    if not p.exists():
        raise WikiError("file_not_found", f"{arg}: no such file.", path=arg)
    if not p.is_file():
        raise WikiError("not_a_file", f"{arg}: not a regular file.", path=arg)
    p = p.resolve()
    if p.suffix.lower() not in FILE_SUFFIXES + HTML_SUFFIXES:
        supported = ", ".join(FILE_SUFFIXES + HTML_SUFFIXES)
        raise WikiError("unsupported_file", f"{arg}: only {supported} files are supported.", path=arg)
    if p.is_relative_to(vault.raw_dir.resolve()):
        raise WikiError(
            "already_in_raw",
            f"{arg} is already inside raw/. Move it outside the vault and add it from there, so capture can "
            "record its provenance.",
            path=arg,
        )
    return p


def _frontmatter_authors(meta: dict | None) -> list[str]:
    """`author`/`authors` from a clipped markdown file's own frontmatter (string or list; [[links]] unwrapped)."""
    if not meta:
        return []
    for key in ("authors", "author"):
        v = meta.get(key)
        if v:
            return fetch_mod.clean_authors(v if isinstance(v, list) else [v])
    return []


def capture_file(vault: Vault, arg: str, now: dt.datetime | None = None) -> dict:
    p = _source_file(vault, arg)
    data = p.read_bytes()
    if b"\x00" in data:
        raise WikiError("binary_file", f"{arg}: looks like a binary file.", path=arg)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise WikiError("not_utf8", f"{arg}: not valid UTF-8 text.", path=arg) from None

    original_meta = None
    body = text
    if p.suffix.lower() == ".md":
        doc = parse(text)
        if doc.meta is not None:
            original_meta, body = doc.meta, doc.body
    body = normalize_text(body)
    sha = content_hash(body)
    dup = find_duplicate(iter_raw(vault), sha)
    if dup:
        return _result(vault, dup, None, {}, duplicate=True)

    now = _now(now)
    title = _file_title(original_meta, body, p.stem)
    meta: dict = {
        "kind": "file",
        "title": title,
        "authors": _frontmatter_authors(original_meta) or None,
        "original_path": str(p),
        "captured_at": _stamp(now),
        "sha256": sha,
    }
    meta = {k: v for k, v in meta.items() if v is not None}
    if original_meta:
        meta["original_frontmatter"] = original_meta
    path = raw_path_for(vault, now.astimezone().date(), title, sha)
    _write_new(path, dump(meta, body + "\n" if body else ""))
    return _result(vault, None, path, meta, duplicate=False)


def capture_saved_html(vault: Vault, arg: str, url: str | None = None, now: dt.datetime | None = None) -> dict:
    """Capture a browser-saved HTML page. Offline; companion `<name>_files/` folders are ignored."""
    p = _source_file(vault, arg)
    data = p.read_bytes()
    saved = fetch_mod.extract_saved(data, url_hint=url)
    page = saved.page
    body = normalize_text(page.body)
    sha = content_hash(body)
    dup = find_duplicate(iter_raw(vault), sha, page.normalized_url)
    if dup:
        res = _result(vault, dup, None, {}, duplicate=True)
        res["url_source"] = saved.url_source
        return res

    now = _now(now)
    path = raw_path_for(vault, now.astimezone().date(), page.title, sha)
    orig = vault.orig_dir / f"{path.name[: -len(EXT)]}.html"
    orig_rel = nfc(orig.relative_to(vault.root).as_posix())
    if saved.url:
        meta: dict = {
            "kind": "url",
            "title": page.title,
            "authors": page.authors or None,
            "original_url": page.original_url,
            "canonical_url": page.canonical_url,
            "normalized_url": page.normalized_url,
            "captured_at": _stamp(now),
            "captured_via": "saved-file",
            "published": page.published,
            "language": page.language,
            "extractor": page.extractor,
            "sha256": sha,
            "original_path": str(p),
            "original_file": orig_rel,
        }
    else:
        meta = {
            "kind": "file",
            "title": page.title,
            "authors": page.authors or None,
            "captured_at": _stamp(now),
            "captured_via": "saved-file",
            "language": page.language,
            "extractor": page.extractor,
            "sha256": sha,
            "original_path": str(p),
            "original_file": orig_rel,
        }
    meta = {k: v for k, v in meta.items() if v is not None}
    orig.parent.mkdir(parents=True, exist_ok=True)
    with orig.open("xb") as f:
        f.write(data)
    _write_new(path, dump(meta, body + "\n"))
    res = _result(vault, None, path, meta, duplicate=False)
    res["url_source"] = saved.url_source
    if saved.url is None:
        res["warnings"] = [
            f"No original URL found in {p.name} (no canonical, og:url or saved-from signal); captured as a "
            "file. Re-add with --url <url> after deleting the raw file if you know the address."
        ]
    return res


def is_url(arg: str) -> bool:
    return bool(_URL.match(arg))


def is_html_file(arg: str) -> bool:
    return Path(arg).suffix.lower() in HTML_SUFFIXES


def capture(vault: Vault, arg: str, now: dt.datetime | None = None, url: str | None = None) -> dict:
    if is_url(arg):
        if url is not None:
            raise WikiError("invalid_option", "--url is only valid for saved .html/.htm files, not for URLs.")
        return capture_url(vault, arg, now)
    if is_html_file(arg):
        return capture_saved_html(vault, arg, url=url, now=now)
    if url is not None:
        raise WikiError("invalid_option", "--url is only valid for saved .html/.htm files.")
    return capture_file(vault, arg, now)


# --- re-derived metadata (read-only) ---------------------------------------------------

_META_FIELDS = ("title", "authors", "published", "language", "canonical_url")


def derive_meta(vault: Vault, raw: RawSource) -> tuple[dict | None, str | None]:
    """Re-extract metadata from the raw file's stored original. Returns (derived, error_code)."""
    m = raw.meta or {}
    orig_rel = m.get("original_file")
    orig = vault.root / orig_rel if isinstance(orig_rel, str) and orig_rel else None
    if orig is None or not orig.is_file():
        return None, "no_original"
    hint = m.get("original_url") if isinstance(m.get("original_url"), str) else None
    try:
        page = fetch_mod.extract_saved(orig.read_bytes(), url_hint=hint or None).page
    except WikiError as e:
        return None, e.code
    return {
        "title": page.title,
        "authors": page.authors,
        "published": page.published,
        "language": page.language,
        "canonical_url": page.canonical_url,
    }, None


def _page_authors(page: Page | None) -> list:
    a = (page.meta or {}).get("authors") if page else None
    return a if isinstance(a, list) else []


def source_meta(vault: Vault, raw_arg: str) -> dict:
    rel = resolve_raw_arg(vault, raw_arg)
    raw = next(r for r in iter_raw(vault) if r.rel == rel)
    pages = iter_pages(vault)
    by_rel = {p.rel: p for p in pages}
    source_pages = ingested_by(pages).get(rel, [])
    derived, error = derive_meta(vault, raw)
    recorded = {k: (raw.meta or {}).get(k) for k in _META_FIELDS}
    return {
        "path": rel,
        "source_page": source_pages[0] if source_pages else None,
        "source_page_authors": _page_authors(by_rel.get(source_pages[0])) if source_pages else [],
        "derivable": derived is not None,
        "error": error if error not in (None, "no_original") else None,
        "recorded": recorded,
        "derived": derived,
    }


def missing_authors_report(vault: Vault) -> dict:
    """Raw files with known authors (recorded, else re-derived) whose source page lacks `authors`."""
    pages = iter_pages(vault)
    by_rel = {p.rel: p for p in pages}
    ingested = ingested_by(pages)
    items = []
    raws = iter_raw(vault)
    for raw in raws:
        src = (ingested.get(raw.rel) or [None])[0]
        if src and _page_authors(by_rel.get(src)):
            continue
        recorded = (raw.meta or {}).get("authors")
        if isinstance(recorded, list) and recorded:
            authors, origin = recorded, "recorded"
        else:
            derived, _ = derive_meta(vault, raw)
            authors, origin = (derived or {}).get("authors") or [], "derived"
        if authors:
            items.append({"raw": raw.rel, "source_page": src, "authors": authors, "from": origin})
    return {"checked": len(raws), "items": items}
