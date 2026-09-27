import os
import shutil
import subprocess

import pytest

from llmwiki.morph import Analyzer
from llmwiki.searchcache import LemmaCache
from llmwiki.vault import Vault

WORDS = ["кошек", "людей", "шёл", "running", "42"]


def _run(vault: Vault) -> tuple[Analyzer, LemmaCache]:
    cache = LemmaCache(vault)
    an = Analyzer(cache.load())
    for w in WORDS:
        an.keys(w)
    cache.save(an.new)
    return an, cache


def test_second_run_analyses_nothing(tmp_vault):
    v = Vault(tmp_vault.root)
    first, _ = _run(v)
    assert len(first.new) == len(WORDS)
    second, cache = _run(v)
    assert second.new == {}
    assert second.keys("кошек") == first.keys("кошек")
    assert cache.warnings == []
    assert (tmp_vault.root / ".llmwiki" / "cache" / ".gitignore").read_text().splitlines()[-1] == "*"


def test_version_change_clears(tmp_vault, monkeypatch):
    v = Vault(tmp_vault.root)
    _run(v)
    monkeypatch.setattr("llmwiki.searchcache.versions", lambda: "different-version")
    cache = LemmaCache(v)
    assert cache.load() == {}
    cache.save({"x": frozenset({"x"})})
    assert set(LemmaCache(v).load()) == {"x"}  # old rows were dropped


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_status_stays_clean(tmp_vault):
    root = tmp_vault.root
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    before = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout
    _run(Vault(root))
    after = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout
    assert after == before
    assert (root / ".llmwiki" / "cache" / "lemmas.sqlite").is_file()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_unwritable_cache_dir(tmp_vault):
    root = tmp_vault.root
    (root / ".llmwiki").mkdir()
    os.chmod(root / ".llmwiki", 0o500)
    try:
        an, cache = _run(Vault(root))
        assert an.keys("кошек") >= {"кошка"}
        assert cache.warnings and "safe to delete" in cache.warnings[0]
    finally:
        os.chmod(root / ".llmwiki", 0o700)


def test_corrupted_database(tmp_vault):
    d = tmp_vault.root / ".llmwiki" / "cache"
    d.mkdir(parents=True)
    (d / "lemmas.sqlite").write_bytes(b"this is not a sqlite database at all" * 10)
    an, cache = _run(Vault(tmp_vault.root))
    assert an.keys("людей") >= {"человек"}
    assert cache.warnings
