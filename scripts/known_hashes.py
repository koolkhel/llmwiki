#!/usr/bin/env python3
"""Maintain src/llmwiki/templates/known_hashes.json: hashes of every template-managed
vault file content that any version of `wiki init` has produced. `wiki upgrade` uses it
to tell untouched files (safe to replace) from user-edited ones.

    python scripts/known_hashes.py            # add the current templates' hashes
    python scripts/known_hashes.py --from-git # (re)seed from every commit in git history

Entries are only ever added, never removed. Run after changing any template;
tests/test_upgrade.py fails until the registry covers the current templates.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from llmwiki.scaffold import render_workflow  # noqa: E402
from llmwiki.upgrade import REGISTRY_PATH, UNMANAGED, content_hash, current_files  # noqa: E402

TEMPLATES = "src/llmwiki/templates"


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def _dest(part: str) -> str:
    return "." + part[4:] if part.startswith("dot-") else part


def historical_files(commit: str) -> dict[str, str]:
    """Vault path -> content exactly as `wiki init` at `commit` would have written it."""
    scaffold = git("show", f"{commit}:src/llmwiki/scaffold.py")
    prefixed_claude = ".claude/commands/wiki-{name}" in scaffold
    out: dict[str, str] = {}
    for f in git("ls-tree", "-r", "--name-only", commit, TEMPLATES).split():
        rel = f[len(TEMPLATES) + 1:]
        if rel.startswith("vault/"):
            dest = "/".join(_dest(p) for p in rel[len("vault/"):].split("/"))
            out[dest] = git("show", f"{commit}:{f}")
        elif rel.startswith("workflows/") and rel.endswith(".md"):
            # render_workflow's content has not changed since it was introduced (d761b50);
            # only the Claude path depends on the era.
            name = rel.split("/", 1)[1][:-3]
            for dest, text in render_workflow(name, git("show", f"{commit}:{f}")).items():
                if dest.startswith(".claude/commands/") and not prefixed_claude:
                    dest = f".claude/commands/{name}.md"
                out[dest] = text
    return {k: v for k, v in out.items() if k not in UNMANAGED}


def load() -> dict[str, set[str]]:
    if not REGISTRY_PATH.exists():
        return {}
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {k: set(v) for k, v in data["paths"].items()}


def save(paths: dict[str, set[str]]) -> None:
    data = {"version": 1, "paths": {k: sorted(v) for k, v in sorted(paths.items())}}
    REGISTRY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def add(paths: dict[str, set[str]], files: dict[str, str]) -> int:
    added = 0
    for path, text in files.items():
        h = content_hash(text)
        if h not in paths.setdefault(path, set()):
            paths[path].add(h)
            added += 1
    return added


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from-git", action="store_true", help="also add every historical version from git")
    args = ap.parse_args()
    paths = load()
    added = 0
    if args.from_git:
        for commit in git("log", "--format=%H", "--reverse", "--", TEMPLATES).split():
            added += add(paths, historical_files(commit))
    added += add(paths, current_files())
    save(paths)
    total = sum(len(v) for v in paths.values())
    print(f"{REGISTRY_PATH.relative_to(ROOT)}: {len(paths)} paths, {total} hashes ({added} added)")


if __name__ == "__main__":
    main()
