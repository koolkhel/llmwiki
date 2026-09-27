"""Synthetic web pages and a stub for `llmwiki.fetch.http_get` (no network)."""

from __future__ import annotations

from llmwiki.errors import WikiError
from llmwiki.fetch import HttpResponse


def article_html(title: str, n_paragraphs: int = 6, canonical: str | None = None) -> str:
    paras = "".join(
        f"<p>Synthetic paragraph {i} of {title}: widgets, gizmos and sprockets, written to be long "
        f"enough for the extractor. See <a href='https://example.org/ref/{i}'>reference {i}</a>.</p>"
        for i in range(n_paragraphs)
    )
    canon = f"<link rel='canonical' href='{canonical}'>" if canonical else ""
    return (
        f"<html><head><title>{title}</title>{canon}</head><body><nav>Home | About</nav>"
        f"<article><h1>{title}</h1><h2>Background</h2>{paras}"
        f"<ul><li>first point</li><li>second point</li></ul></article>"
        f"<footer>Copyright footer</footer></body></html>"
    )


EMPTY_HTML = "<html><head><title>Nothing</title></head><body><nav>menu</nav></body></html>"


class FakeWeb:
    """Maps URL -> (status, content_type, body str|bytes) or an exception to raise."""

    def __init__(self) -> None:
        self.pages: dict[str, object] = {}
        self.redirects: dict[str, str] = {}
        self.requests: list[str] = []

    def add(self, url: str, html: str | bytes, status: int = 200, content_type: str = "text/html; charset=utf-8"):
        self.pages[url] = (status, content_type, html)

    def fail(self, url: str, error: WikiError) -> None:
        self.pages[url] = error

    def __call__(self, url: str, timeout: float = 30) -> HttpResponse:
        self.requests.append(url)
        final = self.redirects.get(url, url)
        entry = self.pages.get(final)
        if entry is None:
            return HttpResponse(final, 404, "text/html", b"not found", "utf-8")
        if isinstance(entry, Exception):
            raise entry
        status, ctype, body = entry
        data = body.encode("utf-8") if isinstance(body, str) else body
        return HttpResponse(final, status, ctype, data, "utf-8" if "charset" in ctype else None)
