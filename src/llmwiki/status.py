"""Vault status summary."""

from __future__ import annotations

from . import index, log, upgrade
from .pages import iter_pages
from .sources import ingested_by, iter_raw
from .vault import TYPE_DIRS, Vault


def vault_status(vault: Vault) -> dict:
    pages = iter_pages(vault)
    raws = iter_raw(vault)
    ingested = ingested_by(pages)
    pending = [
        {"path": r.rel, "title": r.title, "captured_at": (r.meta or {}).get("captured_at")}
        for r in raws
        if r.rel not in ingested
    ]
    return {
        "vault": str(vault.root),
        "pages": {t: sum(1 for p in pages if p.folder_type == t) for t in TYPE_DIRS},
        "raw": {"total": len(raws), "ingested": len(raws) - len(pending), "pending": len(pending)},
        "pending": pending,
        "index_stale": index.render(pages) != _read(vault.index_path),
        "last_log": log.last_heading(vault),
        "templates": upgrade.freshness(vault),
    }


def _read(path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def render_text(s: dict) -> str:
    pages = ", ".join(f"{n} {t}" for t, n in s["pages"].items())
    lines = [
        f"vault:   {s['vault']}",
        f"pages:   {pages}",
        f"raw:     {s['raw']['total']} total, {s['raw']['ingested']} ingested, {s['raw']['pending']} pending",
    ]
    lines += [f"  pending: {p['path']}" for p in s["pending"]]
    lines.append(f"index:   {'STALE (run `wiki index`)' if s['index_stale'] else 'up to date'}")
    lines.append(f"log:     {s['last_log'] or '(no entries)'}")
    t = s["templates"]
    parts = [f"{len(t[k])} {k}" for k in ("outdated", "edited", "missing", "obsolete") if t[k]]
    if t["pending_merge"]:
        parts.append(f"{len(t['pending_merge'])} pending merge ({', '.join(t['pending_merge'])})")
    hint = " - run `wiki upgrade`" if any(t[k] for k in ("outdated", "missing", "obsolete")) else ""
    lines.append(f"templates: {', '.join(parts) + hint if parts else 'up to date'}")
    return "\n".join(lines)
