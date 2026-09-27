import pytest
import requests

from fakeweb import EMPTY_HTML, FakeWeb, article_html
from llmwiki import fetch
from llmwiki.errors import WikiError


@pytest.fixture
def web(monkeypatch):
    fw = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", fw)
    return fw


def test_success_markdown_and_metadata(web):
    web.add("https://example.org/post", article_html("Synthetic Widgets", canonical="/post"))
    page = fetch.fetch("https://example.org/post")
    assert page.title == "Synthetic Widgets"
    assert page.extractor == "trafilatura"
    assert "## Background" in page.body
    assert "- first point" in page.body
    assert "[reference 0](https://example.org/ref/0)" in page.body
    assert "Copyright footer" not in page.body
    assert page.canonical_url == "https://example.org/post"
    assert page.language == "en"
    assert page.html_bytes.startswith(b"<html>")


def test_tracking_params_normalised(web):
    web.add("https://example.org/post?utm_source=feed&utm_medium=x", article_html("T"))
    page = fetch.fetch("https://example.org/post?utm_source=feed&utm_medium=x")
    assert "utm_" not in page.normalized_url
    assert page.original_url.endswith("utm_medium=x")


def test_redirect_final_url(web):
    web.redirects["https://short.example/x"] = "https://example.org/long"
    web.add("https://example.org/long", article_html("Redirected"))
    page = fetch.fetch("https://short.example/x")
    assert page.final_url == "https://example.org/long"


@pytest.mark.parametrize(
    "setup, code",
    [
        (lambda w: w.add("https://e.org/a", "gone", status=410), "http_error"),
        (lambda w: None, "http_error"),  # 404 from the fake
        (lambda w: w.add("https://e.org/a", EMPTY_HTML), "extraction_failed"),
        (lambda w: w.add("https://e.org/a", b"%PDF-1.4", content_type="application/pdf"), "unsupported_content"),
        (lambda w: w.fail("https://e.org/a", WikiError("fetch_timeout", "t")), "fetch_timeout"),
    ],
)
def test_failures(web, setup, code):
    setup(web)
    with pytest.raises(WikiError) as e:
        fetch.fetch("https://e.org/a")
    assert e.value.code == code


def test_http_get_maps_requests_errors(monkeypatch):
    def timeout(*a, **k):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "get", timeout)
    with pytest.raises(WikiError) as e:
        fetch.http_get("https://e.org/a")
    assert e.value.code == "fetch_timeout"

    def conn(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "get", conn)
    with pytest.raises(WikiError) as e:
        fetch.http_get("https://e.org/a")
    assert e.value.code == "fetch_failed"


def test_non_utf8_charset(web):
    html = article_html("Café Synthetic").encode("latin-1")
    web.add("https://e.org/l1", html, content_type="text/html; charset=iso-8859-1")
    assert fetch.fetch("https://e.org/l1").title == "Café Synthetic"
