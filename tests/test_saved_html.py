"""Capturing browser-saved web pages (capture-saved-html change). All pages are synthetic."""

from __future__ import annotations

import datetime as dt

import pytest

from fakeweb import FakeWeb
from llmwiki import fetch, sources
from llmwiki.errors import WikiError
from llmwiki.pages import parse
from llmwiki.vault import Vault


def saved_page(
    title: str = "Synthetic Saved Article",
    canonical: str | None = None,
    og_url: str | None = None,
    saved_from: str | None = None,
    paragraphs: int = 6,
) -> str:
    head = ""
    if saved_from:
        head += f"<!-- saved from url=({len(saved_from):04d}){saved_from} -->\n"
    meta = f"<title>{title}</title>"
    if canonical:
        meta += f'<link rel="canonical" href="{canonical}">'
    if og_url:
        meta += f'<meta property="og:url" content="{og_url}">'
    body = "".join(
        f"<p>Synthetic paragraph {i} of {title}: widgets, gizmos and sprockets, written to be long "
        f"enough for the extractor to treat it as the main article text.</p>"
        for i in range(paragraphs)
    )
    return (
        f"{head}<!DOCTYPE html><html><head>{meta}</head><body><nav>Home | About | Subscribe</nav>"
        f"<article><h1>{title}</h1><h2>Background</h2>{body}</article>"
        f"<footer>Copyright footer</footer></body></html>"
    )


# --- 1.1 URL signals ------------------------------------------------------------


def test_bits_each_signal():
    bits = fetch._html_bits(saved_page(canonical="https://example.org/c", og_url="https://example.org/o",
                                       saved_from="https://example.org/s"))
    assert (bits.canonical, bits.og_url, bits.saved_from) == (
        "https://example.org/c", "https://example.org/o", "https://example.org/s")
    assert bits.title == "Synthetic Saved Article"


def test_bits_relative_canonical_resolved_against_other_signal():
    bits = fetch._html_bits(saved_page(canonical="/post", og_url="https://example.org/other"))
    assert bits.canonical == "https://example.org/post"


def test_bits_relative_canonical_without_base_is_dropped():
    assert fetch._html_bits(saved_page(canonical="/post")).canonical is None


@pytest.mark.parametrize("value", ["file:///Users/x/page.html", "javascript:void(0)", "mailto:a@b.c", "not a url"])
def test_bits_non_http_values_rejected(value):
    bits = fetch._html_bits(saved_page(canonical=value, og_url=value))
    assert bits.canonical is None and bits.og_url is None


def test_bits_none():
    bits = fetch._html_bits(saved_page())
    assert (bits.canonical, bits.og_url, bits.saved_from) == (None, None, None)


def test_bits_base_url_used_for_url_capture():
    assert fetch._html_bits(saved_page(canonical="/p"), "https://example.org/x").canonical == "https://example.org/p"


# --- 1.2 extract_saved ----------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs, url, source",
    [
        (dict(canonical="https://e.org/c", og_url="https://e.org/o", saved_from="https://e.org/s"), "https://e.org/c", "canonical"),
        (dict(og_url="https://e.org/o", saved_from="https://e.org/s"), "https://e.org/o", "og:url"),
        (dict(saved_from="https://e.org/s"), "https://e.org/s", "saved-from"),
    ],
)
def test_detection_order(kwargs, url, source):
    sp = fetch.extract_saved(saved_page(**kwargs).encode())
    assert (sp.url, sp.url_source) == (url, source)
    assert sp.page.original_url == url and sp.page.normalized_url
    assert "## Background" in sp.page.body and "Copyright footer" not in sp.page.body


def test_option_wins():
    sp = fetch.extract_saved(saved_page(canonical="https://e.org/c").encode(), url_hint="https://e.org/real")
    assert (sp.url, sp.url_source, sp.page.original_url) == ("https://e.org/real", "option", "https://e.org/real")


def test_option_must_be_http():
    with pytest.raises(fetch.WikiError) as e:
        fetch.extract_saved(saved_page().encode(), url_hint="example.org/no-scheme")
    assert e.value.code == "invalid_url"


def test_no_url_drops_url_fields():
    sp = fetch.extract_saved(saved_page().encode())
    assert (sp.url, sp.url_source) == (None, None)
    assert sp.page.normalized_url is None and sp.page.canonical_url is None and sp.page.original_url == ""
    assert sp.page.title == "Synthetic Saved Article" and "Synthetic paragraph 0" in sp.page.body


def test_nothing_extractable():
    with pytest.raises(fetch.WikiError) as e:
        fetch.extract_saved(b"<html><head><title>x</title></head><body><nav>menu</nav></body></html>")
    assert e.value.code == "extraction_failed"


def test_non_utf8_saved_page():
    data = saved_page(title="Café Saved", canonical="https://e.org/c").replace(
        "<head>", '<head><meta charset="iso-8859-1">').encode("latin-1")
    assert fetch.extract_saved(data).page.title == "Café Saved"


# --- 1.3 offline, enforced by the code (not by conftest) ------------------------


def test_saved_capture_is_offline_without_test_harness_help(monkeypatch, tmp_path):
    import socket

    import tldextract

    attempts = []

    def record(*args, **kwargs):
        attempts.append(args[:2])
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket.socket, "connect", record)
    monkeypatch.setattr(socket, "create_connection", record)
    monkeypatch.setattr(socket, "getaddrinfo", record)

    # Undo conftest's offline patch: a default, network-using extractor with an empty cache.
    monkeypatch.setattr(tldextract, "extract", tldextract.TLDExtract(cache_dir=str(tmp_path / "tld-cache")))
    tldextract.extract("https://sanity.example.org/")  # sanity: the default does try the network
    assert attempts, "sanity check failed: default tldextract made no network attempt"

    attempts.clear()
    monkeypatch.setattr(tldextract, "extract", tldextract.TLDExtract(cache_dir=str(tmp_path / "tld-cache-2")))
    sp = fetch.extract_saved(saved_page(canonical="https://example.org/post?utm_source=x").encode())
    assert sp.page.normalized_url and "utm_" not in sp.page.normalized_url
    assert attempts == []


# --- 2.1 capture_saved_html ---------------------------------------------------------

NOW = dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.timezone.utc)


def _save(tmp_path, html: str, name: str = "Saved Article _ Site.html", with_assets: bool = True):
    f = tmp_path / "downloads" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(html, encoding="utf-8")
    if with_assets:
        assets = f.with_name(f.stem + "_files")
        assets.mkdir()
        (assets / "style.css").write_text("body{}")
    return f


def _meta(vault, rel):
    return parse((vault.root / rel).read_text(encoding="utf-8")).meta


@pytest.fixture
def vault(tmp_vault):
    return Vault(tmp_vault.root)


def test_saved_page_with_canonical(vault, tmp_path):
    f = _save(tmp_path, saved_page(canonical="https://example.org/post"))
    before = (f.read_bytes(), f.stat().st_mtime_ns)
    assets_before = sorted(p.name for p in f.with_name(f.stem + "_files").iterdir())
    res = sources.capture(vault, str(f), now=NOW)
    assert res["created"] and res["kind"] == "url" and res["url_source"] == "canonical"
    m = _meta(vault, res["path"])
    assert m["kind"] == "url" and m["captured_via"] == "saved-file"
    assert m["original_url"] == "https://example.org/post" and m["canonical_url"] == "https://example.org/post"
    assert m["normalized_url"] and m["extractor"] == "trafilatura" and m["language"] == "en"
    assert m["original_path"] == str(f.resolve())
    assert (vault.root / m["original_file"]).read_bytes() == before[0]  # byte-exact copy
    assert m["original_file"].startswith("raw/.orig/") and m["original_file"].endswith(".html")
    assert (f.read_bytes(), f.stat().st_mtime_ns) == before  # saved file untouched
    assert sorted(p.name for p in f.with_name(f.stem + "_files").iterdir()) == assets_before
    assert not list(vault.orig_dir.glob("*_files*"))  # assets not copied
    body = parse((vault.root / res["path"]).read_text()).body
    assert "## Background" in body and "Subscribe" not in body


def test_og_and_saved_from(vault, tmp_path):
    a = sources.capture(vault, str(_save(tmp_path, saved_page("One", og_url="https://e.org/one"), "a.html")), now=NOW)
    b = sources.capture(vault, str(_save(tmp_path, saved_page("Two", saved_from="https://e.org/two"), "b.htm")), now=NOW)
    assert _meta(vault, a["path"])["original_url"] == "https://e.org/one" and a["url_source"] == "og:url"
    assert _meta(vault, b["path"])["original_url"] == "https://e.org/two" and b["url_source"] == "saved-from"


def test_explicit_url_wins(vault, tmp_path):
    f = _save(tmp_path, saved_page(canonical="https://e.org/wrong"))
    res = sources.capture(vault, str(f), now=NOW, url="https://e.org/real")
    assert _meta(vault, res["path"])["original_url"] == "https://e.org/real" and res["url_source"] == "option"


def test_no_url_known(vault, tmp_path):
    res = sources.capture(vault, str(_save(tmp_path, saved_page())), now=NOW)
    m = _meta(vault, res["path"])
    assert m["kind"] == "file" and "original_url" not in m and "normalized_url" not in m
    assert m["captured_via"] == "saved-file" and (vault.root / m["original_file"]).is_file()
    assert res["url_source"] is None and "--url" in res["warnings"][0]


def test_duplicate_saved_after_direct(vault, tmp_path, monkeypatch):
    web = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", web)
    web.add("https://example.org/post", saved_page("Direct", paragraphs=8))
    direct = sources.capture(vault, "https://example.org/post", now=NOW)
    f = _save(tmp_path, saved_page("Saved later", canonical="https://example.org/post?utm_source=x"))
    res = sources.capture(vault, str(f), now=NOW)
    assert res["created"] is False and res["duplicate_of"] == direct["path"]
    assert len(list(vault.raw_dir.glob("*.md"))) == 1 and len(list(vault.orig_dir.iterdir())) == 1


def test_duplicate_direct_after_saved(vault, tmp_path, monkeypatch):
    saved = sources.capture(vault, str(_save(tmp_path, saved_page("Saved", canonical="https://example.org/post"))), now=NOW)
    web = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", web)
    web.add("https://example.org/post?utm_medium=y", saved_page("Direct later", paragraphs=9))
    res = sources.capture(vault, "https://example.org/post?utm_medium=y", now=NOW)
    assert res["duplicate_of"] == saved["path"]


def test_same_saved_file_twice(vault, tmp_path):
    f = _save(tmp_path, saved_page())
    first = sources.capture(vault, str(f), now=NOW)
    again = sources.capture(vault, str(f), now=NOW)
    assert again["duplicate_of"] == first["path"]


def test_nothing_extractable_writes_nothing(vault, tmp_path):
    f = _save(tmp_path, "<html><head><title>x</title><link rel='canonical' href='https://e.org/x'></head>"
                        "<body><nav>menu</nav></body></html>")
    with pytest.raises(WikiError) as e:
        sources.capture(vault, str(f), now=NOW)
    assert e.value.code == "extraction_failed"
    assert not list(vault.raw_dir.glob("*.md")) and not list(vault.orig_dir.iterdir())


@pytest.mark.parametrize("arg_kind", ["txt", "url"])
def test_url_option_rejected_for_other_sources(vault, tmp_path, arg_kind):
    arg = "https://example.org/x"
    if arg_kind == "txt":
        (tmp_path / "notes.txt").write_text("synthetic")
        arg = str(tmp_path / "notes.txt")
    with pytest.raises(WikiError) as e:
        sources.capture(vault, arg, now=NOW, url="https://example.org")
    assert e.value.code == "invalid_option"
    assert not list(vault.raw_dir.glob("*.md"))


# --- 2.2 CLI ----------------------------------------------------------------------


def test_cli_saved_page_json(run_cli, tmp_vault, tmp_path):
    f = _save(tmp_path, saved_page(canonical="https://example.org/post"))
    r = run_cli("add-source", f, "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out + r.err
    doc = r.json()
    assert doc["kind"] == "url" and doc["url_source"] == "canonical" and doc["status"] == "pending"
    assert "warnings" not in doc


def test_cli_url_option(run_cli, tmp_vault, tmp_path):
    f = _save(tmp_path, saved_page())
    doc = run_cli("add-source", f, "--url", "https://example.org/given", "--json", "--vault", tmp_vault.root).json()
    assert doc["url_source"] == "option" and doc["kind"] == "url"


def test_cli_no_url_warning_json_and_stderr(run_cli, tmp_vault, tmp_path):
    r = run_cli("add-source", _save(tmp_path, saved_page(), "a.html", False), "--json", "--vault", tmp_vault.root)
    assert r.code == 0 and any("--url" in w for w in r.json()["warnings"])
    r = run_cli("add-source", _save(tmp_path, saved_page("Other"), "b.html", False), "--vault", tmp_vault.root)
    assert r.code == 0 and "--url" in r.err and "no URL" in r.out


def test_cli_text_output(run_cli, tmp_vault, tmp_path):
    r = run_cli("add-source", _save(tmp_path, saved_page(og_url="https://e.org/o")), "--vault", tmp_vault.root)
    assert "saved page, URL from og:url" in r.out


@pytest.mark.parametrize("arg_kind", ["txt", "url"])
def test_cli_url_option_rejected(run_cli, tmp_vault, tmp_path, arg_kind):
    arg = "https://example.org/x"
    if arg_kind == "txt":
        (tmp_path / "n.txt").write_text("synthetic")
        arg = str(tmp_path / "n.txt")
    r = run_cli("add-source", arg, "--url", "https://example.org", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "invalid_option"


def test_cli_extraction_failed_exit_2(run_cli, tmp_vault, tmp_path):
    f = _save(tmp_path, "<html><head><title>x</title></head><body><nav>m</nav></body></html>")
    r = run_cli("add-source", f, "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "extraction_failed"
