import pytest

from fakeweb import FakeWeb, article_html
from llmwiki import fetch


@pytest.fixture
def web(monkeypatch):
    fw = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", fw)
    return fw


def test_url_success(run_cli, web, tmp_vault):
    web.add("https://example.org/post", article_html("CLI Capture"))
    r = run_cli("add-source", "https://example.org/post", "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out + r.err
    doc = r.json()
    assert doc["status"] == "pending" and doc["created"] is True
    assert doc["path"].startswith("raw/") and doc["path"].endswith("-CLI Capture.md")
    assert len(doc["sha256"]) == 64
    assert (tmp_vault.root / doc["path"]).is_file()
    assert len(list((tmp_vault.root / "raw" / ".orig").glob("*.html"))) == 1


def test_url_failure_nothing_written(run_cli, web, tmp_vault):
    r = run_cli("add-source", "https://example.org/missing", "--json", "--vault", tmp_vault.root)
    assert r.code == 2
    assert r.json()["error"]["code"] == "http_error"
    assert not list((tmp_vault.root / "raw").glob("*.md"))
    assert not list((tmp_vault.root / "raw" / ".orig").iterdir())


def test_duplicate_reported(run_cli, web, tmp_vault):
    web.add("https://example.org/post", article_html("Twice"))
    first = run_cli("add-source", "https://example.org/post", "--json", "--vault", tmp_vault.root).json()
    web.add("https://example.org/post?utm_campaign=z", article_html("Twice"))
    again = run_cli("add-source", "https://example.org/post?utm_campaign=z", "--json", "--vault", tmp_vault.root)
    assert again.code == 0
    assert again.json()["duplicate_of"] == first["path"] and again.json()["created"] is False
    assert len(list((tmp_vault.root / "raw").glob("*.md"))) == 1


def test_file_capture_leaves_original(run_cli, tmp_vault, tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("synthetic text file body\n")
    before = (src.read_bytes(), src.stat().st_mtime_ns)
    r = run_cli("add-source", src, "--json", "--vault", tmp_vault.root)
    assert r.code == 0
    assert r.json()["kind"] == "file"
    assert (src.read_bytes(), src.stat().st_mtime_ns) == before


def test_rejects_directory_and_binary(run_cli, tmp_vault, tmp_path):
    binf = tmp_path / "b.txt"
    binf.write_bytes(b"\x00\x01")
    for arg, code in ((tmp_path, "not_a_file"), (binf, "binary_file")):
        r = run_cli("add-source", arg, "--json", "--vault", tmp_vault.root)
        assert r.code == 2 and r.json()["error"]["code"] == code
    assert not list((tmp_vault.root / "raw").glob("*.md"))


def test_missing_argument_is_usage_error(run_cli, tmp_vault):
    r = run_cli("add-source", "--vault", tmp_vault.root)
    assert r.code == 2


def test_text_output(run_cli, tmp_vault, tmp_path):
    src = tmp_path / "t.txt"
    src.write_text("hello synthetic\n")
    r = run_cli("add-source", src, "--vault", tmp_vault.root)
    assert r.out.startswith("captured raw/") and "(pending)" in r.out
