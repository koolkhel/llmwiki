"""CLI-wide contract: JSON output, error shape, exit codes."""

import json

import pytest

from llmwiki import cli
from llmwiki.errors import WikiError
from llmwiki.vault import find_vault


@pytest.fixture
def probe_command():
    """Register a throwaway command exercising the shared plumbing."""

    @cli.app.command("probe")
    def probe(
        json_: cli.JsonOpt = False,
        vault: cli.VaultOpt = None,
        fail: bool = False,
        problems: bool = False,
    ) -> None:
        def body() -> cli.Outcome:
            v = find_vault(vault)
            if fail:
                raise WikiError("probe_failed", "probe asked to fail")
            return cli.Outcome({"vault": str(v.root)}, f"vault {v.root}", exit_code=1 if problems else 0,
                               warnings=["a warning"])

        cli.run(json_, body)

    yield
    cli.app.registered_commands.pop()


def test_json_success_is_single_document(probe_command, run_cli, tmp_vault):
    r = run_cli("probe", "--json", "--vault", tmp_vault.root)
    assert r.code == 0
    doc = json.loads(r.out)  # raises if more than one document / extra text
    assert doc["vault"] == str(tmp_vault.root.resolve())
    assert doc["warnings"] == ["a warning"]


def test_text_mode_warnings_go_to_stderr(probe_command, run_cli, tmp_vault):
    r = run_cli("probe", "--vault", tmp_vault.root)
    assert r.code == 0
    assert "a warning" in r.err and "a warning" not in r.out


def test_json_error_shape_and_exit_2(probe_command, run_cli, tmp_vault):
    r = run_cli("probe", "--json", "--vault", tmp_vault.root, "--fail")
    assert r.code == 2
    assert r.json() == {"error": {"code": "probe_failed", "message": "probe asked to fail"}}


def test_problems_exit_1(probe_command, run_cli, tmp_vault):
    assert run_cli("probe", "--vault", tmp_vault.root, "--problems").code == 1


def test_no_vault_exit_2(probe_command, run_cli, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = run_cli("probe", "--json")
    assert r.code == 2
    assert r.json()["error"]["code"] == "vault_not_found"
    r = run_cli("probe")
    assert r.code == 2 and "--vault" in r.err


def test_usage_error_exit_2_json(probe_command, run_cli):
    r = run_cli("probe", "--json", "--no-such-option")
    assert r.code == 2
    assert r.json()["error"]["code"] == "usage_error"


def test_unknown_command_exit_2(run_cli):
    r = run_cli("no-such-command")
    assert r.code == 2
    assert r.out == ""
