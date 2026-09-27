"""URL fetching and main-text extraction.

We fetch the page ourselves (so the exact HTML can be kept), use
mediacloud-metadata for metadata (normalized URL, title, language, date) and
trafilatura for a markdown body, falling back to mediacloud's text when
trafilatura finds nothing. `http_get` is the single network seam.
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from . import __version__
from .errors import WikiError

USER_AGENT = f"llmwiki/{__version__} (personal knowledge-base source capture)"
TIMEOUT_SECONDS = 30
# Below this, "extracted text" is boilerplate (e.g. a nav label), not an article.
MIN_BODY_CHARS = 40
_HTML_TYPES = {"text/html", "application/xhtml+xml", "application/xml", "text/xml"}


@dataclass
class HttpResponse:
    url: str  # final URL after redirects
    status: int
    content_type: str
    content: bytes
    encoding: str | None  # declared charset, if any


@dataclass
class FetchedPage:
    original_url: str
    final_url: str
    html_bytes: bytes
    title: str
    body: str  # markdown
    normalized_url: str | None  # None only for saved pages without a known URL
    canonical_url: str | None
    published: str | None
    language: str | None
    extractor: str


def http_get(url: str, timeout: float = TIMEOUT_SECONDS) -> HttpResponse:
    import requests

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except requests.Timeout:
        raise WikiError("fetch_timeout", f"Timed out after {timeout}s fetching {url}.", url=url) from None
    except requests.RequestException as e:
        raise WikiError("fetch_failed", f"Could not fetch {url}: {e}", url=url) from None
    ctype = r.headers.get("content-type", "")
    return HttpResponse(r.url, r.status_code, ctype, r.content, r.encoding if "charset" in ctype.lower() else None)


def _decode(content: bytes, encoding: str | None) -> str:
    if encoding:
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            pass
    from bs4 import UnicodeDammit

    return UnicodeDammit(content, is_html=True).unicode_markup or ""


def _offline_suffix_list() -> None:
    """Make tldextract (used by mcmetadata) use its bundled public-suffix snapshot.

    Its default instance downloads the list on first use, which would break the
    "no network except add-source <URL>" rule for saved-page capture.
    """
    import tldextract

    if not getattr(tldextract.extract, "_llmwiki_offline", False):
        offline = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
        offline._llmwiki_offline = True
        tldextract.extract = offline


def _extractors():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import mcmetadata
        import trafilatura
    _offline_suffix_list()
    mcmetadata.ignore_loggers()
    for name in ("trafilatura", "htmldate", "courlan", "readability", "newspaper", "goose3"):
        logging.getLogger(name).setLevel(logging.ERROR)
    return mcmetadata, trafilatura


_SAVED_FROM = re.compile(r"<!--\s*saved from url=\(\d+\)(\S+?)\s*-->", re.I)


@dataclass
class HtmlBits:
    """Signals read straight from the markup."""

    title: str | None
    canonical: str | None
    og_url: str | None
    saved_from: str | None  # Chrome/IE "<!-- saved from url=(NNNN)URL -->"


def _http_url(u: str | None) -> str | None:
    if not u:
        return None
    parts = urlsplit(u)
    return u if parts.scheme in ("http", "https") and parts.netloc else None


def _html_bits(html: str, base_url: str | None = None) -> HtmlBits:
    """Title and URL signals from the markup. Relative URLs are resolved against `base_url`,
    else against another absolute signal on the page; only absolute http(s) URLs are kept."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    canonical = None
    for link in soup.find_all("link", href=True):
        rel = link.get("rel") or []
        if "canonical" in [r.lower() for r in (rel if isinstance(rel, list) else [rel])]:
            canonical = link["href"].strip()
            break
    og = soup.find("meta", attrs={"property": "og:url"}) or soup.find("meta", attrs={"name": "og:url"})
    og_url = og.get("content", "").strip() if og else None
    m = _SAVED_FROM.search(html[:4096])
    saved_from = m.group(1) if m else None
    base = base_url or next((u for u in (canonical, og_url, saved_from) if _http_url(u)), None)

    def resolve(u: str | None) -> str | None:
        if not u:
            return None
        return _http_url(urljoin(base, u) if base else u)

    return HtmlBits(title or None, resolve(canonical), resolve(og_url), _http_url(saved_from))


def extract(original_url: str, final_url: str, html: str, html_bytes: bytes) -> FetchedPage:
    mcmetadata, trafilatura = _extractors()
    try:
        meta = mcmetadata.extract(url=final_url, html_text=html)
    except Exception:  # e.g. BadContentError for short pages; body may still be extractable
        meta = {}
    body = trafilatura.extract(
        html, url=final_url, include_formatting=True, include_links=True, include_tables=True
    )
    extractor = "trafilatura"
    if len((body or "").strip()) < MIN_BODY_CHARS:
        body = meta.get("text_content") or ""
        extractor = f"mcmetadata:{meta.get('text_extraction_method') or 'unknown'}"
    if len(body.strip()) < MIN_BODY_CHARS:
        raise WikiError("extraction_failed", f"No main text could be extracted from {final_url}.", url=final_url)

    bits = _html_bits(html, final_url)
    html_title, canonical = bits.title, bits.canonical
    normalized = meta.get("normalized_url")
    if not normalized:
        try:
            normalized = mcmetadata.urls.normalize_url(final_url)
        except Exception:
            normalized = None
    published = meta.get("publication_date")
    parts = urlsplit(final_url)
    return FetchedPage(
        original_url=original_url,
        final_url=final_url,
        html_bytes=html_bytes,
        title=(meta.get("article_title") or html_title or f"{parts.netloc}{parts.path}").strip(),
        body=body.strip() + "\n",
        normalized_url=normalized or final_url,
        canonical_url=canonical,
        published=published.isoformat() if hasattr(published, "isoformat") else (published or None),
        language=meta.get("language") or None,
        extractor=extractor,
    )


# Stand-in URL so extraction runs for a saved page whose real URL is unknown;
# URL-derived fields are discarded afterwards.
_PLACEHOLDER_URL = "file:///saved-page.html"


@dataclass
class SavedPage:
    page: FetchedPage
    url: str | None
    url_source: str | None  # "option" | "canonical" | "og:url" | "saved-from" | None


def extract_saved(data: bytes, url_hint: str | None = None) -> SavedPage:
    """Extract a browser-saved HTML page. Makes no network requests."""
    html = _decode(data, None)
    if url_hint is not None:
        if not _http_url(url_hint.strip()):
            raise WikiError("invalid_url", f"--url must be an absolute http(s) URL, got {url_hint!r}.", url=url_hint)
        url, source = url_hint.strip(), "option"
    else:
        bits = _html_bits(html)
        url, source = next(
            ((u, src) for src, u in (("canonical", bits.canonical), ("og:url", bits.og_url),
                                     ("saved-from", bits.saved_from)) if u),
            (None, None),
        )
    page = extract(url or _PLACEHOLDER_URL, url or _PLACEHOLDER_URL, html, data)
    if url is None:
        page.original_url = page.final_url = ""
        page.normalized_url = page.canonical_url = None
    return SavedPage(page, url, source)


def fetch(url: str) -> FetchedPage:
    resp = http_get(url)
    if resp.status >= 400:
        raise WikiError("http_error", f"HTTP {resp.status} fetching {url}.", url=url, status=resp.status)
    base_type = resp.content_type.split(";")[0].strip().lower()
    if base_type and base_type not in _HTML_TYPES:
        raise WikiError(
            "unsupported_content",
            f"{url} returned {base_type}; only HTML pages are supported. Save it as .txt/.md and add the file instead.",
            url=url,
            content_type=base_type,
        )
    return extract(url, resp.url, _decode(resp.content, resp.encoding), resp.content)
