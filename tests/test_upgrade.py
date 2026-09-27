"""Vault template upgrades (vault-upgrade change)."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

from llmwiki import upgrade
from llmwiki.vault import Vault


def missing_from_registry() -> list[str]:
    from llmwiki.languages import LANGUAGES

    reg = upgrade.registry()
    return sorted({p for lang in (None, *LANGUAGES) for p, text in upgrade.current_files(lang).items()
                   if upgrade.content_hash(text) not in reg.get(p, ())})


# --- 1.2 registry completeness -------------------------------------------------------


def test_registry_covers_current_templates():
    missing = missing_from_registry()
    assert not missing, f"templates changed without updating the registry: run `python scripts/known_hashes.py` ({missing})"


def test_registry_check_catches_unregistered_template_change(monkeypatch):
    real = upgrade.current_files()
    monkeypatch.setattr(upgrade, "current_files",
                        lambda lang=None: {**real, "AGENTS.md": real["AGENTS.md"] + "\nnew rule\n"})
    assert missing_from_registry() == ["AGENTS.md"]


def test_hash_normalises_crlf():
    assert upgrade.content_hash("a\r\nb\n") == upgrade.content_hash("a\nb\n")
    assert upgrade.content_hash("a\nb") != upgrade.content_hash("a\nb\n")  # trailing newline counts as an edit


# --- 3.1 upgrade engine ------------------------------------------------------------------


ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("known_hashes_script", ROOT / "scripts" / "known_hashes.py")
known_hashes_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(known_hashes_script)

BOOTSTRAP = "f8720ae"  # first release: full schema in CLAUDE.md, unprefixed .claude/commands


def _git_available():
    return shutil.which("git") and subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", BOOTSTRAP],
                                                  capture_output=True).returncode == 0


needs_history = pytest.mark.skipif(not _git_available(), reason="needs the repo's git history")


def old_vault(tmp_path: Path, commit: str = BOOTSTRAP, name: str = "old") -> Path:
    """A vault exactly as `wiki init` at `commit` wrote it, plus some content."""
    root = tmp_path / name
    for d in ("raw/.orig", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/analyses"):
        (root / d).mkdir(parents=True)
    for rel, text in known_hashes_script.historical_files(commit).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (root / "llmwiki.toml").write_text('layout_version = 1\ncreated = "2026-01-01"\n')
    (root / "log.md").write_text("# Log\n\n## [2026-01-01 00:00] init | vault created\n")
    (root / "index.md").write_text("<!-- generated -->\n# Index\n")
    (root / "raw" / "2026-01-01-X.md").write_text("---\nkind: file\nsha256: x\n---\nsynthetic raw\n")
    (root / "wiki" / "concepts" / "C.md").write_text("---\ntype: concept\n---\nsynthetic page\n")
    return root


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts}


def _actions(report):
    return {i["path"]: i["action"] for i in report["items"]}


@needs_history
def test_untouched_bootstrap_vault(tmp_path):
    root = old_vault(tmp_path)
    report, warnings = upgrade.run(Vault(root))
    a = _actions(report)
    assert a["AGENTS.md"] == "create" and a["CLAUDE.md"] == "update"
    for wf in ("ingest", "query", "lint", "upgrade"):
        assert a[f".claude/commands/wiki-{wf}.md"] == "create"
        assert a[f".agents/skills/wiki-{wf}/SKILL.md"] == "create"
    for wf in ("ingest", "query", "lint"):
        assert a[f".claude/commands/{wf}.md"] == "delete"
        assert not (root / ".claude" / "commands" / f"{wf}.md").exists()
    assert "conflict" not in a.values() and "keep" not in a.values()
    assert (root / "CLAUDE.md").read_text().strip().endswith("@AGENTS.md")
    assert upgrade.current_files() == {p: (root / p).read_text() for p in upgrade.current_files()}
    assert warnings == []


def test_edited_agents_md_conflict(tmp_path, run_cli):
    root = tmp_path / "v"
    run_cli("init", root, "--no-git")
    (root / "AGENTS.md").write_text((root / "AGENTS.md").read_text() + "\n## My own rules\n\n- keep this\n")
    mine = (root / "AGENTS.md").read_text()
    report, _ = upgrade.run(Vault(root))
    item = next(i for i in report["items"] if i["path"] == "AGENTS.md")
    assert item == {"path": "AGENTS.md", "action": "conflict", "new_path": "AGENTS.md.new"}
    assert (root / "AGENTS.md").read_text() == mine
    assert (root / "AGENTS.md.new").read_text() == upgrade.current_files()["AGENTS.md"]


@needs_history
def test_edited_obsolete_command_kept(tmp_path):
    root = old_vault(tmp_path)
    old = root / ".claude" / "commands" / "ingest.md"
    old.write_text(old.read_text() + "\nMy extra ingest step.\n")
    report, warnings = upgrade.run(Vault(root))
    item = next(i for i in report["items"] if i["path"] == ".claude/commands/ingest.md")
    assert item["action"] == "keep" and item["replaced_by"] == ".claude/commands/wiki-ingest.md"
    assert old.exists() and (root / ".claude" / "commands" / "wiki-ingest.md").exists()
    assert any("wiki-ingest.md" in w and "ingest.md" in w for w in warnings)


@needs_history
def test_dry_run_writes_nothing(tmp_path, run_cli):
    root = old_vault(tmp_path)
    before = _snapshot(root)
    r = run_cli("upgrade", "--dry-run", "--json", "--vault", root)
    assert r.code == 0 and r.json()["dry_run"] is True and r.json()["counts"]["delete"] == 3
    assert _snapshot(root) == before
    assert "would delete" in run_cli("upgrade", "--dry-run", "--vault", root).out


@needs_history
def test_content_untouched(tmp_path):
    root = old_vault(tmp_path)
    content = ["raw/2026-01-01-X.md", "wiki/concepts/C.md", "index.md", "log.md", "llmwiki.toml"]
    before = {p: (root / p).read_bytes() for p in content}
    upgrade.run(Vault(root))
    assert {p: (root / p).read_bytes() for p in content} == before


@needs_history
def test_idempotent(tmp_path):
    root = old_vault(tmp_path)
    (root / "CLAUDE.md").write_text("# my own CLAUDE.md\n")  # edited -> conflict both times
    upgrade.run(Vault(root))
    after_first = _snapshot(root)
    report, _ = upgrade.run(Vault(root))
    assert set(_actions(report).values()) <= {"unchanged", "conflict"}
    assert _snapshot(root) == after_first


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_dirty_git_warning(tmp_path, run_cli):
    root = tmp_path / "v"
    run_cli("init", root)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@example.org", "-c", "user.name=T",
                    "commit", "-qm", "init"], check=True)
    (root / "AGENTS.md").write_text((root / "AGENTS.md").read_text() + "\nlocal edit\n")
    r = run_cli("upgrade", "--json", "--vault", root)
    assert r.code == 0
    assert any("Uncommitted changes" in w and "AGENTS.md" in w for w in r.json()["warnings"])


def test_fresh_vault_all_unchanged(tmp_path, run_cli):
    root = tmp_path / "v"
    run_cli("init", root, "--no-git")
    doc = run_cli("upgrade", "--json", "--vault", root).json()
    assert set(_actions(doc).values()) == {"unchanged"} and "warnings" not in doc


# --- 4.1 status and lint -------------------------------------------------------------------


@needs_history
def test_status_reports_outdated_and_obsolete(tmp_path, run_cli):
    root = old_vault(tmp_path)
    t = run_cli("status", "--json", "--vault", root).json()["templates"]
    assert "CLAUDE.md" in t["outdated"] and "AGENTS.md" in t["missing"]
    assert ".claude/commands/ingest.md" in t["obsolete"]
    assert "run `wiki upgrade`" in run_cli("status", "--vault", root).out


def test_status_fresh_vault(tmp_path, run_cli):
    root = tmp_path / "v"
    run_cli("init", root, "--no-git")
    t = run_cli("status", "--json", "--vault", root).json()["templates"]
    assert t == {"outdated": [], "edited": [], "missing": [], "obsolete": [], "pending_merge": []}
    assert "templates: up to date" in run_cli("status", "--vault", root).out


def test_pending_merge_in_status_and_lint(tmp_path, run_cli):
    root = tmp_path / "v"
    run_cli("init", root, "--no-git")
    (root / "AGENTS.md").write_text("# edited schema\n")
    upgrade.run(Vault(root))
    t = run_cli("status", "--json", "--vault", root).json()["templates"]
    assert t["edited"] == ["AGENTS.md"] and t["pending_merge"] == ["AGENTS.md.new"]
    r = run_cli("lint", "--strict", "--json", "--vault", root)
    assert r.code == 0  # info only
    assert [(f["code"], f["path"]) for f in r.json()["findings"]] == [("template_merge_pending", "AGENTS.md.new")]
    assert "pending merge" in run_cli("status", "--vault", root).out


def test_status_is_read_only(tmp_path, run_cli):
    root = tmp_path / "v"
    run_cli("init", root, "--no-git")
    (root / "AGENTS.md").write_text("# edited schema\n")
    before = _snapshot(root)
    run_cli("status", "--vault", root)
    run_cli("lint", "--vault", root)
    assert _snapshot(root) == before
