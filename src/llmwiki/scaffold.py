"""`wiki init`: scaffold a vault from the packaged templates.

Templates live in `templates/vault/`. Path parts named `dot-x` are installed
as `.x` (so packaging tools don't treat them as hidden or as ignore files).
Existing files are never modified.
"""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
from collections.abc import Iterator
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from . import index, log
from .errors import WikiError
from .vault import LAYOUT_VERSION, TYPE_DIRS, Vault

DIRS = ("raw", "raw/.orig", "wiki", *(f"wiki/{d}" for d in TYPE_DIRS.values()))


def _templates() -> Traversable:
    return files("llmwiki") / "templates" / "vault"


def _walk(node: Traversable, parts: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Traversable]]:
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        if child.is_dir():
            yield from _walk(child, (*parts, child.name))
        else:
            yield (*parts, child.name), child


def template_files() -> list[str]:
    """Destination paths (vault-relative) of all packaged template files."""
    return ["/".join(_dest(p) for p in parts) for parts, _ in _walk(_templates())]


def _dest(part: str) -> str:
    return "." + part[4:] if part.startswith("dot-") else part


def _git_state(root: Path, want_git: bool) -> str:
    if not want_git:
        return "skipped"
    git = shutil.which("git")
    if git is None:
        return "unavailable"
    inside = subprocess.run([git, "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True)
    if inside.returncode == 0:
        return "existing"
    subprocess.run([git, "-C", str(root), "init", "-q"], check=True, capture_output=True)
    return "initialized"


def init_vault(target: Path, git: bool = True, today: dt.date | None = None) -> tuple[dict, list[str]]:
    root = Path(target).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise WikiError("not_a_directory", f"{root} exists and is not a directory.", path=str(root))
    root.mkdir(parents=True, exist_ok=True)
    today = today or dt.date.today()
    created: list[str] = []
    skipped: list[str] = []

    for d in DIRS:
        p = root / d
        if not p.is_dir():
            p.mkdir(parents=True)
            created.append(f"{d}/")

    values = {"{{layout_version}}": str(LAYOUT_VERSION), "{{date}}": today.isoformat()}
    for parts, node in _walk(_templates()):
        rel = "/".join(_dest(p) for p in parts)
        dest = root / rel
        if dest.exists():
            skipped.append(rel)
            continue
        text = node.read_text(encoding="utf-8")
        for k, v in values.items():
            text = text.replace(k, v)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("x", encoding="utf-8") as f:
            f.write(text)
        created.append(rel)

    vault = Vault(root)
    if vault.index_path.exists():
        skipped.append("index.md")
    else:
        vault.index_path.write_text(index.expected(vault), encoding="utf-8")
        created.append("index.md")
    if "log.md" in created:
        log.append(vault, "init", "vault created")

    git_state = _git_state(root, git)
    warnings = []
    if shutil.which("wiki") is None:
        exe = Path(sys.executable).parent / "wiki"
        warnings.append(
            "`wiki` is not on PATH, but the vault's Claude Code commands call it by name. "
            f"Fix: mkdir -p ~/.local/bin && ln -sf {exe} ~/.local/bin/wiki (and ensure ~/.local/bin is on PATH)."
        )
    return {"vault": str(root), "created": created, "skipped": skipped, "git": git_state}, warnings


def render_text(res: dict) -> str:
    lines = [f"vault: {res['vault']}"]
    lines += [f"  created  {p}" for p in res["created"]]
    lines += [f"  skipped  {p} (exists)" for p in res["skipped"]]
    lines.append(f"git: {res['git']}")
    lines.append(f"next: cd {res['vault']} && claude   # then /ingest <url or file>")
    return "\n".join(lines)
