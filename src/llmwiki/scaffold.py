"""`wiki init`: scaffold a vault from the packaged templates.

Templates live in `templates/vault/`. Path parts named `dot-x` are installed
as `.x` (so packaging tools don't treat them as hidden or as ignore files).
Each workflow in `templates/workflows/` is rendered twice, from the same body:
as a Claude Code command and as a Kimi Code (`.agents/skills`) skill.
Existing files are never modified.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from . import index, log
from .errors import WikiError
from .languages import LANGUAGES, schema_values, supported
from .vault import LAYOUT_VERSION, TYPE_DIRS, Vault

DIRS = ("raw", "raw/.orig", "wiki", *(f"wiki/{d}" for d in TYPE_DIRS.values()))
SCHEMA_IMPORT = "@AGENTS.md"
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def _templates() -> Traversable:
    return files("llmwiki") / "templates" / "vault"


def _workflows() -> Traversable:
    return files("llmwiki") / "templates" / "workflows"


def _split_workflow(text: str) -> tuple[dict[str, str], str]:
    """Frontmatter as raw `key: value` strings (not YAML-parsed, so values pass through verbatim) and body."""
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError("workflow template lacks frontmatter")
    fields = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep:
            fields[k.strip()] = v.strip()
    return fields, text[m.end():]


def render_workflow(name: str, text: str) -> dict[str, str]:
    """Vault-relative path -> content, for both agents."""
    fm, body = _split_workflow(text)
    claude = [f"description: {fm['description']}"]
    if "argument-hint" in fm:
        claude.append(f"argument-hint: {fm['argument-hint']}")
    kimi = [f"name: wiki-{name}", f"description: {fm['description']}"]
    return {
        f".claude/commands/wiki-{name}.md": "---\n" + "\n".join(claude) + "\n---\n" + body,
        f".agents/skills/wiki-{name}/SKILL.md": "---\n" + "\n".join(kimi) + "\n---\n" + body,
    }


def planned_files(values: dict[str, str] | None = None, language: str | None = None) -> dict[str, str]:
    """Every file `init` writes (except index.md), vault-relative path -> content."""
    out: dict[str, str] = {}
    all_values = {**schema_values(language), **(values or {})}
    for parts, node in _walk(_templates()):
        text = node.read_text(encoding="utf-8")
        for k, v in all_values.items():
            text = text.replace(k, v)
        out["/".join(_dest(p) for p in parts)] = text
    for node in sorted(_workflows().iterdir(), key=lambda c: c.name):
        if node.name.endswith(".md"):
            out.update(render_workflow(node.name[:-3], node.read_text(encoding="utf-8")))
    return out


def _walk(node: Traversable, parts: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Traversable]]:
    for child in sorted(node.iterdir(), key=lambda c: c.name):
        if child.name.startswith(".") or child.name == "__pycache__":
            continue
        if child.is_dir():
            yield from _walk(child, (*parts, child.name))
        else:
            yield (*parts, child.name), child


def template_files() -> list[str]:
    """Destination paths (vault-relative) of all files rendered from packaged templates."""
    return list(planned_files())


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


def init_vault(
    target: Path, git: bool = True, today: dt.date | None = None, language: str | None = None
) -> tuple[dict, list[str]]:
    if language is not None and language not in LANGUAGES:
        raise WikiError("invalid_language", f"--language {language!r} is not supported. Supported: {supported()}.")
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
    for rel, text in planned_files(values, language).items():
        dest = root / rel
        if dest.exists():
            skipped.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("x", encoding="utf-8") as f:
            f.write(text)
        created.append(rel)

    claude_md = root / "CLAUDE.md"
    legacy_schema = "CLAUDE.md" in skipped and SCHEMA_IMPORT not in (
        line.strip() for line in claude_md.read_text(encoding="utf-8").splitlines()
    )

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
            "`wiki` is not on PATH, but the vault's agent workflows call it by name. "
            f"Fix: mkdir -p ~/.local/bin && ln -sf {exe} ~/.local/bin/wiki (and ensure ~/.local/bin is on PATH)."
        )
    if legacy_schema:
        warnings.append(
            "CLAUDE.md predates the shared AGENTS.md schema and was left unchanged. Merge any customisations "
            f"into AGENTS.md, then replace CLAUDE.md with the single line `{SCHEMA_IMPORT}`."
        )
    return {"vault": str(root), "language": language, "created": created, "skipped": skipped, "git": git_state}, warnings


def render_text(res: dict) -> str:
    lines = [f"vault: {res['vault']}"]
    if res.get("language"):
        lines.append(f"language: {LANGUAGES[res['language']]} ({res['language']})")
    lines += [f"  created  {p}" for p in res["created"]]
    lines += [f"  skipped  {p} (exists)" for p in res["skipped"]]
    lines.append(f"git: {res['git']}")
    lines.append(f"next: cd {res['vault']} && claude   # then /wiki-ingest <url or file>")
    lines.append(f"  or: cd {res['vault']} && kimi     # then /skill:wiki-ingest <url or file>")
    return "\n".join(lines)
