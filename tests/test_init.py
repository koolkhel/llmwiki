import json
import shutil
import subprocess

import pytest

from llmwiki import scaffold
from llmwiki.pages import iter_md

EXPECTED = [
    "llmwiki.toml", "CLAUDE.md", "index.md", "log.md", ".gitignore",
    ".claude/commands/ingest.md", ".claude/commands/query.md", ".claude/commands/lint.md",
    ".claude/settings.json",
]
EXPECTED_DIRS = ["raw", "raw/.orig", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/analyses"]


def test_fresh_init(run_cli, tmp_path):
    target = tmp_path / "wikis" / "research"
    r = run_cli("init", target, "--json", "--no-git")
    assert r.code == 0, r.out + r.err
    doc = r.json()
    for f in EXPECTED:
        assert (target / f).is_file(), f
        assert f in doc["created"]
    for d in EXPECTED_DIRS:
        assert (target / d).is_dir(), d
    assert doc["skipped"] == []
    assert run_cli("status", "--vault", target).code == 0
    assert "layout_version = 1" in (target / "llmwiki.toml").read_text()
    assert "{{" not in (target / "llmwiki.toml").read_text()
    assert "] init | vault created" in (target / "log.md").read_text()


def test_fresh_vault_lints_clean(run_cli, tmp_path):
    target = tmp_path / "v"
    run_cli("init", target, "--no-git")
    r = run_cli("lint", "--json", "--strict", "--vault", target)
    assert r.code == 0
    assert r.json()["findings"] == []


def test_reinit_preserves_edits(run_cli, tmp_path):
    target = tmp_path / "v"
    run_cli("init", target, "--no-git")
    (target / "CLAUDE.md").write_text("# my evolved schema\n")
    (target / ".claude" / "commands" / "query.md").unlink()
    log_before = (target / "log.md").read_text()
    doc = run_cli("init", target, "--json", "--no-git").json()
    assert (target / "CLAUDE.md").read_text() == "# my evolved schema\n"
    assert "CLAUDE.md" in doc["skipped"]
    assert doc["created"] == [".claude/commands/query.md"]
    assert (target / "log.md").read_text() == log_before  # no second init entry


def test_existing_directory_contents_untouched(run_cli, tmp_path):
    target = tmp_path / "v"
    (target / "wiki" / "concepts").mkdir(parents=True)
    (target / "notes.txt").write_text("keep me")
    run_cli("init", target, "--no-git")
    assert (target / "notes.txt").read_text() == "keep me"


def test_no_git(run_cli, tmp_path):
    run_cli("init", tmp_path / "v", "--no-git")
    assert not (tmp_path / "v" / ".git").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_init_without_commits(run_cli, tmp_path):
    doc = run_cli("init", tmp_path / "v", "--json").json()
    assert doc["git"] == "initialized"
    assert (tmp_path / "v" / ".git").is_dir()
    head = subprocess.run(["git", "-C", str(tmp_path / "v"), "rev-parse", "HEAD"], capture_output=True)
    assert head.returncode != 0  # no commits
    assert run_cli("init", tmp_path / "v", "--json").json()["git"] == "existing"


def test_path_warning(run_cli, tmp_path, monkeypatch):
    real_which = shutil.which
    monkeypatch.setattr(scaffold.shutil, "which", lambda n: None if n == "wiki" else real_which(n))
    r = run_cli("init", tmp_path / "v", "--json", "--no-git")
    assert r.code == 0
    assert any("not on PATH" in w for w in r.json()["warnings"])
    r = run_cli("init", tmp_path / "v2", "--no-git")
    assert "not on PATH" in r.err


def test_target_is_file(run_cli, tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    r = run_cli("init", f, "--json")
    assert r.code == 2 and r.json()["error"]["code"] == "not_a_directory"


def test_gitignore_and_obsidian(run_cli, tmp_path):
    target = tmp_path / "v"
    run_cli("init", target, "--no-git")
    assert ".obsidian/workspace" in (target / ".gitignore").read_text()
    (target / ".obsidian").mkdir()
    (target / ".obsidian" / "note-like.md").write_text("x")
    (target / "wiki" / ".obsidian").mkdir()
    (target / "wiki" / ".obsidian" / "x.md").write_text("x")
    assert list(iter_md(target / "wiki")) == []
    assert run_cli("lint", "--strict", "--vault", target).code == 0


def test_settings_json_is_valid(run_cli, tmp_path):
    run_cli("init", tmp_path / "v", "--no-git")
    settings = json.loads((tmp_path / "v" / ".claude" / "settings.json").read_text())
    assert "Bash(wiki:*)" in settings["permissions"]["allow"]
    assert any("raw" in rule for rule in settings["permissions"]["deny"])


def test_claude_md_states_raw_immutability(run_cli, tmp_path):
    run_cli("init", tmp_path / "v", "--no-git")
    text = (tmp_path / "v" / "CLAUDE.md").read_text()
    assert "Never edit, rename or delete anything under `raw/`" in text
    assert "wiki add-source" in text


def test_template_list_matches():
    assert sorted(scaffold.template_files()) == sorted(f for f in EXPECTED if f != "index.md")
