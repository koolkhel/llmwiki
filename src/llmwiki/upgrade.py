"""`wiki upgrade`: bring a vault's template-managed files up to date without losing edits.

Every file content any version of `wiki init` produced is recorded (as a hash) in
`templates/known_hashes.json`. A vault file matching a known hash is untouched and
can be replaced; anything else was edited by the user and gets a `<path>.new` instead.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .scaffold import planned_files
from .vault import Vault
from .vault import language as vault_language

REGISTRY_PATH = Path(__file__).resolve().parent / "templates" / "known_hashes.json"
# Rendered by init but not template-managed: placeholders / content that the vault owns.
UNMANAGED = frozenset({"llmwiki.toml", "log.md"})


def content_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def current_files(language: str | None = None) -> dict[str, str]:
    """Template-managed vault path -> current content, for a vault's wiki language."""
    return {k: v for k, v in planned_files(language=language).items() if k not in UNMANAGED}


def registry() -> dict[str, frozenset[str]]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {k: frozenset(v) for k, v in data["paths"].items()}


# --- planning ------------------------------------------------------------------------

ACTIONS = ("create", "update", "unchanged", "conflict", "delete", "keep")


@dataclass
class Item:
    path: str
    action: str  # one of ACTIONS
    new_path: str | None = None  # for conflicts: where the current template is written
    replaced_by: str | None = None  # for obsolete paths: the path that supersedes it
    pending_merge: bool = False  # a <path>.new already exists

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, False)}


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _replacement(obsolete: str, current: dict[str, str]) -> str | None:
    parent, _, name = obsolete.rpartition("/")
    candidate = f"{parent}/wiki-{name}" if parent else f"wiki-{name}"
    return candidate if candidate in current else None


def plan(vault: Vault) -> list[Item]:
    """What `wiki upgrade` would do. Reads only template-managed files."""
    reg = registry()
    current = current_files(vault_language(vault))
    items: list[Item] = []
    for path, text in current.items():
        f = vault.root / path
        pending = (vault.root / f"{path}.new").exists()
        if not f.exists():
            items.append(Item(path, "create", pending_merge=pending))
            continue
        existing = _read(f)
        h = content_hash(existing) if existing is not None else None
        if h == content_hash(text):
            action = "unchanged"
        elif h is not None and h in reg.get(path, ()):
            action = "update"
        else:
            action = "conflict"
        items.append(Item(path, action, new_path=f"{path}.new" if action == "conflict" else None,
                          pending_merge=pending))
    for path in sorted(set(reg) - set(current)):
        f = vault.root / path
        if not f.exists():
            continue
        existing = _read(f)
        pristine = existing is not None and content_hash(existing) in reg[path]
        items.append(Item(path, "delete" if pristine else "keep", replaced_by=_replacement(path, current)))
    return items


# --- applying --------------------------------------------------------------------------


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _dirty_managed(vault: Vault, items: list[Item]) -> list[str]:
    git = shutil.which("git")
    if git is None:
        return []
    inside = subprocess.run([git, "-C", str(vault.root), "rev-parse", "--is-inside-work-tree"], capture_output=True)
    if inside.returncode != 0:
        return []
    paths = [i.path for i in items if (vault.root / i.path).exists()]
    if not paths:
        return []
    out = subprocess.run([git, "-C", str(vault.root), "status", "--porcelain", "--", *paths],
                         capture_output=True, text=True)
    return [line[3:] for line in out.stdout.splitlines() if line.strip()]


def run(vault: Vault, dry_run: bool = False) -> tuple[dict, list[str]]:
    """Plan and (unless dry_run) apply. Returns (report, warnings)."""
    items = plan(vault)
    warnings: list[str] = []
    dirty = _dirty_managed(vault, items)
    if dirty:
        warnings.append(
            "Uncommitted changes to template files (" + ", ".join(dirty) + "); commit first so the upgrade "
            "can be reviewed or undone with git."
        )
    for i in items:
        if i.action == "keep":
            target = f" into {i.replaced_by}" if i.replaced_by else ""
            warnings.append(f"{i.path} was edited but is no longer used; merge your edits{target}, then delete it.")
    if not dry_run:
        current = current_files(vault_language(vault))
        for i in items:
            if i.action in ("create", "update"):
                _atomic_write(vault.root / i.path, current[i.path])
            elif i.action == "conflict":
                _atomic_write(vault.root / i.new_path, current[i.path])
            elif i.action == "delete":
                (vault.root / i.path).unlink()
    counts = {a: sum(1 for i in items if i.action == a) for a in ACTIONS}
    report = {"vault": str(vault.root), "dry_run": dry_run, "counts": counts, "items": [i.to_dict() for i in items]}
    return report, warnings


def render_text(report: dict) -> str:
    verbs = {"create": "create", "update": "update", "conflict": "conflict", "delete": "delete", "keep": "keep"}
    prefix = "would " if report["dry_run"] else ""
    lines = []
    for i in report["items"]:
        if i["action"] == "unchanged":
            continue
        extra = f" -> {i['new_path']}" if i.get("new_path") else ""
        if i.get("replaced_by"):
            extra = f" (replaced by {i['replaced_by']})"
        lines.append(f"  {prefix}{verbs[i['action']]:<8} {i['path']}{extra}")
    c = report["counts"]
    lines.append(
        f"{c['create']} created, {c['update']} updated, {c['delete']} deleted, {c['conflict']} conflict(s), "
        f"{c['keep']} kept, {c['unchanged']} unchanged" + (" (dry run)" if report["dry_run"] else "")
    )
    if c["conflict"] or c["keep"]:
        lines.append("next: run the upgrade workflow (/wiki-upgrade in Claude Code, /skill:wiki-upgrade in Kimi Code) "
                     "to merge your edits")
    return "\n".join(lines)


def freshness(vault: Vault) -> dict:
    """Template status for `wiki status` / `wiki lint`. Read-only."""
    items = plan(vault)

    def paths(*actions: str) -> list[str]:
        return [i.path for i in items if i.action in actions]

    return {
        "outdated": paths("update"),
        "edited": paths("conflict"),
        "missing": paths("create"),
        "obsolete": paths("delete", "keep"),
        "pending_merge": [f"{i.path}.new" for i in items if i.pending_merge],
    }
