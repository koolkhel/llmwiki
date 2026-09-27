import pytest

from llmwiki.errors import WikiError
from llmwiki.vault import find_vault


def test_nearest_ancestor(tmp_vault):
    sub = tmp_vault.root / "wiki" / "concepts"
    assert find_vault(env={}, cwd=sub).root == tmp_vault.root.resolve()


def test_env_var(tmp_vault, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    v = find_vault(env={"LLMWIKI_VAULT": str(tmp_vault.root)}, cwd=elsewhere)
    assert v.root == tmp_vault.root.resolve()


def test_explicit_beats_env(tmp_vault, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "llmwiki.toml").write_text("layout_version = 1\n")
    v = find_vault(explicit=other, env={"LLMWIKI_VAULT": str(tmp_vault.root)})
    assert v.root == other.resolve()


def test_explicit_non_vault(tmp_path):
    with pytest.raises(WikiError) as e:
        find_vault(explicit=tmp_path, env={})
    assert e.value.code == "not_a_vault"


def test_not_found(tmp_path):
    with pytest.raises(WikiError) as e:
        find_vault(env={}, cwd=tmp_path)
    assert e.value.code == "vault_not_found"
    assert "--vault" in e.value.message
