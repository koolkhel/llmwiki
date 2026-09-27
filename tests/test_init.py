import json
import shutil
import subprocess

import pytest

from llmwiki import scaffold
from llmwiki.pages import iter_md

WORKFLOWS = ("ingest", "query", "lint")
EXPECTED = [
    "llmwiki.toml", "AGENTS.md", "CLAUDE.md", "index.md", "log.md", ".gitignore", ".claude/settings.json",
    *(f".claude/commands/{w}.md" for w in WORKFLOWS),
    *(f".agents/skills/wiki-{w}/SKILL.md" for w in WORKFLOWS),
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
    (target / "AGENTS.md").write_text("# my evolved schema\n")
    (target / ".claude" / "commands" / "query.md").unlink()
    log_before = (target / "log.md").read_text()
    doc = run_cli("init", target, "--json", "--no-git").json()
    assert (target / "AGENTS.md").read_text() == "# my evolved schema\n"
    assert "AGENTS.md" in doc["skipped"]
    assert doc["created"] == [".claude/commands/query.md"]
    assert ".agents/skills/wiki-query/SKILL.md" in doc["skipped"]
    assert "warnings" not in doc or not any("CLAUDE.md" in w for w in doc["warnings"])
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


def test_agents_md_states_raw_immutability(run_cli, tmp_path):
    run_cli("init", tmp_path / "v", "--no-git")
    text = (tmp_path / "v" / "AGENTS.md").read_text()
    assert "Never edit, rename or delete anything under `raw/`" in text
    assert "wiki add-source" in text


def test_template_list_matches():
    assert sorted(scaffold.template_files()) == sorted(f for f in EXPECTED if f != "index.md")


# --- agent-neutral vault -----------------------------------------------------


def _split(text):
    assert text.startswith("---\n")
    fm, _, body = text[4:].partition("\n---\n")
    return fm.splitlines(), body


def test_claude_md_only_imports_agents_md(run_cli, tmp_path):
    run_cli("init", tmp_path / "v", "--no-git")
    lines = [l for l in (tmp_path / "v" / "CLAUDE.md").read_text().splitlines() if l.strip()]
    assert lines[-1] == "@AGENTS.md"
    assert all(l.startswith("<!--") for l in lines[:-1])  # nothing but a comment besides the import
    assert "## Page types" in (tmp_path / "v" / "AGENTS.md").read_text()


@pytest.mark.parametrize("wf", WORKFLOWS)
def test_same_workflow_body_for_both_agents(run_cli, tmp_path, wf):
    v = tmp_path / "v"
    run_cli("init", v, "--no-git")
    claude_fm, claude_body = _split((v / ".claude" / "commands" / f"{wf}.md").read_text())
    kimi_fm, kimi_body = _split((v / ".agents" / "skills" / f"wiki-{wf}" / "SKILL.md").read_text())
    assert claude_body == kimi_body
    assert "$ARGUMENTS" in kimi_body
    assert kimi_fm[0] == f"name: wiki-{wf}" and kimi_fm[1].startswith("description: ")
    assert claude_fm[0] == kimi_fm[1]  # same description
    assert "following `AGENTS.md`" in claude_body


def test_argument_hint_passes_through_verbatim(run_cli, tmp_path):
    run_cli("init", tmp_path / "v", "--no-git")
    fm, _ = _split((tmp_path / "v" / ".claude" / "commands" / "lint.md").read_text())
    assert "argument-hint: [area or tag to focus on]" in fm  # not re-serialised as a YAML list


def test_no_bare_claude_only_workflow_references(run_cli, tmp_path):
    import re

    v = tmp_path / "v"
    run_cli("init", v, "--no-git")
    texts = {"AGENTS.md": (v / "AGENTS.md").read_text()}
    for wf in WORKFLOWS:
        texts[wf] = _split((v / ".claude" / "commands" / f"{wf}.md").read_text())[1]
    for name, text in texts.items():
        for line in text.splitlines():
            for wf in re.findall(r"(?<![\w:-])/(ingest|query|lint)\b", line):
                assert f"/skill:wiki-{wf}" in line, f"{name}: bare /{wf} in: {line}"


def test_no_kimi_permission_files_and_gitignore(run_cli, tmp_path):
    v = tmp_path / "v"
    run_cli("init", v, "--no-git")
    assert not (v / ".kimi-code").exists()
    assert ".kimi-code/local.toml" in (v / ".gitignore").read_text().splitlines()


LEGACY_SCHEMA = "# Wiki schema\n\nThe old full schema, customised by the human.\n"


def test_legacy_claude_md_warns(run_cli, tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    (v / "CLAUDE.md").write_text(LEGACY_SCHEMA)
    r = run_cli("init", v, "--json", "--no-git")
    doc = r.json()
    assert (v / "CLAUDE.md").read_text() == LEGACY_SCHEMA
    assert "CLAUDE.md" in doc["skipped"] and "AGENTS.md" in doc["created"]
    assert (v / ".agents" / "skills" / "wiki-ingest" / "SKILL.md").is_file()
    assert any("@AGENTS.md" in w and "CLAUDE.md" in w for w in doc["warnings"])


def test_migrated_claude_md_no_warning(run_cli, tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    (v / "CLAUDE.md").write_text("<!-- note -->\n@AGENTS.md\n")
    doc = run_cli("init", v, "--json", "--no-git").json()
    assert not any("CLAUDE.md" in w for w in doc.get("warnings", []))


def test_text_output_mentions_both_agents(run_cli, tmp_path):
    r = run_cli("init", tmp_path / "v", "--no-git")
    assert "/ingest" in r.out and "/skill:wiki-ingest" in r.out


def test_schema_and_workflows_cover_authors(run_cli, tmp_path):
    v = tmp_path / "v"
    run_cli("init", v, "--no-git")
    agents = (v / "AGENTS.md").read_text()
    for needle in ("authors:", "## Authors", "tags: [person]", "aliases:", "According to", "--author"):
        assert needle in agents, needle
    for wf in (".claude/commands/ingest.md", ".agents/skills/wiki-ingest/SKILL.md"):
        text = (v / wf).read_text()
        assert "**Authors:**" in text and "tags: [person]" in text
    for wf in (".claude/commands/lint.md", ".agents/skills/wiki-lint/SKILL.md"):
        assert "wiki source-meta --all --json" in (v / wf).read_text()
    assert run_cli("lint", "--strict", "--vault", v).code == 0
