"""Structural health checks. Read-only: never modifies the vault."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass

from . import index, upgrade
from .errors import EXIT_OK, EXIT_PROBLEMS, WikiError
from .links import Resolver, page_links
from .naming import is_canonical_stem, key, title_to_filename
from .pages import iter_pages
from .sources import content_hash, ingested_by, iter_raw
from .vault import PAGE_TYPES, TYPE_DIRS, Vault

SEVERITIES = ("error", "warning", "info")


@dataclass
class Finding:
    severity: str
    code: str
    path: str
    message: str
    target: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def check(vault: Vault) -> list[Finding]:
    pages = iter_pages(vault)
    raws = iter_raw(vault)
    resolver = Resolver(vault, pages)
    out: list[Finding] = []
    raw_authors_by_rel = {
        r.rel: a for r in raws if isinstance(a := (r.meta or {}).get("authors"), list) and a
    }
    raw_published_by_rel = {r.rel: v for r in raws if (v := (r.meta or {}).get("published"))}
    by_key: dict[str, list] = defaultdict(list)
    inbound: dict[str, set[str]] = defaultdict(set)

    for p in pages:
        by_key[key(p.stem)].append(p)

        if not is_canonical_stem(p.fs_stem):
            try:
                hint = f" Rename to {title_to_filename(p.fs_stem)!r}."
            except WikiError:
                hint = ""
            out.append(Finding("error", "bad_filename", p.rel, f"Filename does not follow the naming rules.{hint}"))

        if p.meta is None:
            if p.fm_error == "missing":
                out.append(Finding("error", "frontmatter_missing", p.rel, "Page has no YAML frontmatter."))
            else:
                out.append(Finding("error", "frontmatter_invalid", p.rel, f"Frontmatter is invalid: {p.fm_error}."))
        else:
            problems = p.problems()
            if problems:
                out.append(Finding("error", "frontmatter_invalid", p.rel, "; ".join(problems) + "."))
            if p.folder_type is None:
                out.append(Finding(
                    "error", "type_folder_mismatch", p.rel,
                    f"Pages must live in a type folder: {', '.join(f'wiki/{d}/' for d in TYPE_DIRS.values())}.",
                ))
            elif p.type in PAGE_TYPES and p.type != p.folder_type:
                out.append(Finding(
                    "error", "type_folder_mismatch", p.rel,
                    f"Frontmatter type is {p.type!r} but the page is in wiki/{TYPE_DIRS[p.folder_type]}/.",
                ))
            if not p.summary:
                out.append(Finding("warning", "empty_summary", p.rel, "Summary is empty; index.md shows only the link."))
            raw = p.meta.get("raw")
            if p.folder_type == "source" and isinstance(raw, str) and raw.strip():
                if not (vault.root / raw.strip()).is_file():
                    out.append(Finding("error", "raw_missing", p.rel, f"`raw` points to a missing file: {raw}.", raw))
                raw_published = raw_published_by_rel.get(raw.strip().removeprefix("./"))
                if raw_published and not p.meta.get("published"):
                    out.append(Finding(
                        "warning", "missing_published", p.rel,
                        f"Raw file records published {raw_published} but this page has no `published`.",
                    ))
                raw_authors = raw_authors_by_rel.get(raw.strip().removeprefix("./"))
                page_authors = p.meta.get("authors")
                if raw_authors and not (isinstance(page_authors, list) and page_authors):
                    out.append(Finding(
                        "warning", "missing_authors", p.rel,
                        f"Raw file records authors ({', '.join(map(str, raw_authors))}) but this page has no `authors`.",
                    ))

        for link in page_links(p):
            if not link.target:
                continue
            resolved = resolver.resolve(link.target)
            if resolved is None:
                out.append(Finding("error", "dead_link", p.rel, f"{link.raw} does not resolve to any page or file.",
                                   link.raw))
            elif resolved != p.rel:
                inbound[resolved].add(p.rel)

    for group in by_key.values():
        if len(group) > 1:
            for p in group:
                others = ", ".join(o.rel for o in group if o is not p)
                out.append(Finding("error", "duplicate_title", p.rel, f"Name collides with {others}."))

    for p in pages:
        if not inbound[p.rel]:
            out.append(Finding("warning", "orphan", p.rel, "No other page links here."))

    ingested = ingested_by(pages)
    for r in raws:
        if r.meta is None or not r.sha256:
            out.append(Finding("error", "frontmatter_invalid", r.rel,
                               "Raw file lacks capture frontmatter (sha256); add sources with `wiki add-source`."))
        elif content_hash(r.body) != r.sha256:
            out.append(Finding("error", "raw_modified", r.rel, "Raw file body no longer matches its recorded sha256."))
        if r.rel not in ingested:
            out.append(Finding("info", "pending_source", r.rel, "Not yet ingested (no wiki/sources page has raw: here)."))

    for pending in upgrade.freshness(vault)["pending_merge"]:
        out.append(Finding("info", "template_merge_pending", pending,
                           "Template update not merged yet; run the upgrade workflow (/wiki-upgrade).", pending))

    if index.render(pages) != _read(vault.index_path):
        out.append(Finding("warning", "index_stale", vault.rel(vault.index_path), "Out of date; run `wiki index`."))

    out.sort(key=lambda f: (SEVERITIES.index(f.severity), f.path, f.code, f.target or ""))
    return out


def _read(path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def report(vault: Vault, strict: bool = False) -> tuple[dict, int]:
    findings = check(vault)
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
    failed = counts["error"] > 0 or (strict and counts["warning"] > 0)
    data = {"ok": not failed, "strict": strict, "counts": counts, "findings": [f.to_dict() for f in findings]}
    return data, EXIT_PROBLEMS if failed else EXIT_OK


def render_text(data: dict) -> str:
    lines = [f"{f['severity']:<7} {f['code']:<20} {f['path']}: {f['message']}" for f in data["findings"]]
    c = data["counts"]
    lines.append(f"{c['error']} error(s), {c['warning']} warning(s), {c['info']} info")
    return "\n".join(lines)
