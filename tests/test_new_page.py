from conftest import CASE_DUPES, NFC_TITLE, NFD_TITLE
from llmwiki.pages import parse


def test_create_concept(run_cli, tmp_vault):
    r = run_cli("new-page", "--type", "concept", "Retrieval-Augmented Generation", "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out
    doc = r.json()
    assert doc["path"] == "wiki/concepts/Retrieval-Augmented Generation.md"
    assert doc["link"] == "[[Retrieval-Augmented Generation]]"
    page = parse((tmp_vault.root / doc["path"]).read_text())
    assert list(page.meta)[:6] == ["type", "summary", "sources", "tags", "created", "updated"]
    assert page.meta["type"] == "concept" and page.meta["summary"] == ""
    assert page.meta["sources"] == [] and page.meta["tags"] == []


def test_title_is_sanitised_and_nfc(run_cli, tmp_vault):
    r = run_cli("new-page", "--type", "entity", NFD_TITLE + ": x?", "--json", "--vault", tmp_vault.root)
    assert r.json()["title"] == f"{NFC_TITLE} x"


def test_duplicate_across_folders(run_cli, tmp_vault):
    tmp_vault.page("concept", CASE_DUPES[0])
    r = run_cli("new-page", "--type", "entity", CASE_DUPES[1], "--json", "--vault", tmp_vault.root)
    assert r.code == 2
    err = r.json()["error"]
    assert err["code"] == "duplicate_title"
    assert err["details"]["existing"] == f"wiki/concepts/{CASE_DUPES[0]}.md"
    assert not (tmp_vault.root / "wiki" / "entities" / f"{CASE_DUPES[1]}.md").exists()


def test_source_requires_raw(run_cli, tmp_vault):
    r = run_cli("new-page", "--type", "source", "X", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "invalid_raw"
    assert not list((tmp_vault.root / "wiki" / "sources").iterdir())


def test_source_raw_must_be_under_raw(run_cli, tmp_vault):
    outside = tmp_vault.root / "notes.md"
    outside.write_text("x")
    orig = tmp_vault.root / "raw" / ".orig" / "a.md"
    orig.write_text("x")
    for bad in (str(outside), "raw/missing.md", "raw/.orig/a.md"):
        r = run_cli("new-page", "--type", "source", "X", "--raw", bad, "--json", "--vault", tmp_vault.root)
        assert r.code == 2 and r.json()["error"]["code"] == "invalid_raw", bad
    assert not list((tmp_vault.root / "wiki" / "sources").iterdir())


def test_source_with_raw(run_cli, tmp_vault):
    raw = tmp_vault.raw("2026-01-01-Article", "text")
    r = run_cli("new-page", "--type", "source", "Article", "--raw", tmp_vault.rel(raw), "--json", "--vault", tmp_vault.root)
    assert r.code == 0
    meta = parse((tmp_vault.root / r.json()["path"]).read_text()).meta
    assert meta["raw"] == "raw/2026-01-01-Article.md"


def test_raw_only_for_source(run_cli, tmp_vault):
    raw = tmp_vault.raw("r", "text")
    r = run_cli("new-page", "--type", "concept", "C", "--raw", tmp_vault.rel(raw), "--json", "--vault", tmp_vault.root)
    assert r.code == 2


def test_bad_type_is_usage_error(run_cli, tmp_vault):
    r = run_cli("new-page", "--type", "person", "X", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "usage_error"


def test_empty_title(run_cli, tmp_vault):
    r = run_cli("new-page", "--type", "concept", "???", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "empty_title"
