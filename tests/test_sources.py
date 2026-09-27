import datetime as dt

import pytest

from conftest import EMOJI_TITLE, LONG_CYRILLIC_TITLE
from fakeweb import FakeWeb, article_html
from llmwiki import fetch, sources
from llmwiki.errors import WikiError
from llmwiki.pages import parse
from llmwiki.vault import Vault

NOW = dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def web(monkeypatch):
    fw = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", fw)
    return fw


@pytest.fixture
def vault(tmp_vault):
    return Vault(tmp_vault.root)


def _read(vault, rel):
    return parse((vault.root / rel).read_text(encoding="utf-8"))


def test_url_capture_frontmatter(web, vault):
    web.add("https://example.org/post", article_html("Synthetic Widgets", canonical="https://example.org/post"))
    res = sources.capture(vault, "https://example.org/post", now=NOW)
    assert res["created"] and res["status"] == "pending" and res["duplicate_of"] is None
    assert res["path"] == "raw/2026-09-27-Synthetic Widgets.md"
    doc = _read(vault, res["path"])
    m = doc.meta
    assert m["kind"] == "url"
    assert m["original_url"] == "https://example.org/post"
    assert m["canonical_url"] == "https://example.org/post"
    assert m["normalized_url"]
    assert m["title"] == "Synthetic Widgets"
    assert m["captured_at"] == "2026-09-27T12:00:00Z"
    assert m["language"] == "en" and m["extractor"] == "trafilatura"
    assert m["sha256"] == res["sha256"] == sources.content_hash(doc.body)
    assert "## Background" in doc.body
    orig = vault.root / m["original_file"]
    assert m["original_file"] == "raw/.orig/2026-09-27-Synthetic Widgets.html"
    assert orig.read_bytes() == article_html("Synthetic Widgets", canonical="https://example.org/post").encode()


def test_url_failure_writes_nothing(web, vault):
    web.add("https://example.org/x", "err", status=500)
    with pytest.raises(WikiError):
        sources.capture(vault, "https://example.org/x", now=NOW)
    assert not list(vault.raw_dir.glob("*.md")) and not list(vault.orig_dir.iterdir())


def test_dedup_by_normalized_url(web, vault):
    web.add("https://example.org/post", article_html("Same"))
    # Different content (e.g. updated page), same article via tracking URL.
    web.add("https://example.org/post?utm_source=x", article_html("Same", n_paragraphs=7))
    first = sources.capture(vault, "https://example.org/post", now=NOW)
    second = sources.capture(vault, "https://example.org/post?utm_source=x", now=NOW)
    assert second["created"] is False and second["duplicate_of"] == first["path"]
    assert len(list(vault.raw_dir.glob("*.md"))) == 1


def test_dedup_by_hash_for_files(vault, tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("Same synthetic text.\r\n")
    b.write_text("\nSame synthetic text.\n")
    first = sources.capture(vault, str(a), now=NOW)
    second = sources.capture(vault, str(b), now=NOW)
    assert second["duplicate_of"] == first["path"]


def test_same_title_same_day_distinct_names(vault, tmp_path):
    a = tmp_path / "x.md"
    b = tmp_path / "y.md"
    a.write_text("# Weekly Notes\n\nfirst synthetic body\n")
    b.write_text("# Weekly Notes\n\nsecond synthetic body\n")
    r1 = sources.capture(vault, str(a), now=NOW)
    r2 = sources.capture(vault, str(b), now=NOW)
    assert r1["path"] == "raw/2026-09-27-Weekly Notes.md"
    assert r2["path"] == f"raw/2026-09-27-Weekly Notes-{r2['sha256'][:8]}.md"


def test_file_capture_txt(vault, tmp_path):
    src = tmp_path / "transcript.txt"
    src.write_text("Speaker A: synthetic line.\nSpeaker B: another.\n")
    before = src.read_bytes()
    res = sources.capture(vault, str(src), now=NOW)
    m = _read(vault, res["path"]).meta
    assert m["kind"] == "file" and m["title"] == "transcript"
    assert m["original_path"] == str(src.resolve())
    assert src.read_bytes() == before


def test_md_capture_preserves_frontmatter_and_title(vault, tmp_path):
    src = tmp_path / "clip.md"
    src.write_text(f"---\ntitle: {EMOJI_TITLE}\nsource: somewhere\n---\n# Heading\n\nBody.\n")
    res = sources.capture(vault, str(src), now=NOW)
    doc = _read(vault, res["path"])
    assert doc.meta["title"] == EMOJI_TITLE
    assert doc.meta["original_frontmatter"] == {"title": EMOJI_TITLE, "source": "somewhere"}
    assert doc.body.startswith("# Heading")


def test_md_title_from_heading(vault, tmp_path):
    src = tmp_path / "file-name.md"
    src.write_text("intro\n\n# Real Title #\n\ntext\n")
    assert sources.capture(vault, str(src), now=NOW)["title"] == "Real Title"


def test_long_title_raw_name_fits(vault, tmp_path):
    src = tmp_path / "long.md"
    src.write_text(f"# {LONG_CYRILLIC_TITLE}\n\nbody\n")
    res = sources.capture(vault, str(src), now=NOW)
    assert len(res["path"].split("/")[-1].encode()) <= 200


@pytest.mark.parametrize(
    "make, code",
    [
        (lambda d: d / "missing.txt", "file_not_found"),
        (lambda d: d, "not_a_file"),
        (lambda d: (d / "bin.txt", (d / "bin.txt").write_bytes(b"ab\x00cd"))[0], "binary_file"),
        (lambda d: (d / "l1.txt", (d / "l1.txt").write_bytes("café".encode("latin-1")))[0], "not_utf8"),
        (lambda d: (d / "doc.pdf", (d / "doc.pdf").write_bytes(b"%PDF"))[0], "unsupported_file"),
    ],
)
def test_file_rejections(vault, tmp_path, make, code):
    d = tmp_path / "in"
    d.mkdir()
    with pytest.raises(WikiError) as e:
        sources.capture(vault, str(make(d)), now=NOW)
    assert e.value.code == code
    assert not list(vault.raw_dir.glob("*.md"))


def test_status_is_derived_and_raw_untouched(vault, tmp_vault, tmp_path):
    src = tmp_path / "article.md"
    src.write_text("# Some Article\n\nsynthetic body\n")
    res = sources.capture(vault, str(src), now=NOW)
    raw_path = vault.root / res["path"]
    before = raw_path.read_bytes()
    assert res["status"] == "pending"
    assert sources.source_status(vault, res["path"]) == "pending"

    tmp_vault.page("source", "Some Article", raw=res["path"])
    assert sources.source_status(vault, res["path"]) == "ingested"
    assert raw_path.read_bytes() == before

    # A `raw:` field outside wiki/sources/ does not count.
    tmp_vault.page("concept", "Mentions It", raw="raw/other.md")
    assert sources.source_status(vault, "raw/other.md") == "pending"
