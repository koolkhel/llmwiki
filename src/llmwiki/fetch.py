"""URL fetching and main-text extraction.

We fetch the page ourselves (so the exact HTML can be kept), use
mediacloud-metadata for metadata (normalized URL, title, language, date) and
trafilatura for a markdown body, falling back to mediacloud's text when
trafilatura finds nothing. `http_get` is the single network seam.
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from dataclasses import dataclass, field
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
    authors: list[str] = field(default_factory=list)


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


# --- authors ----------------------------------------------------------------------

_ARTICLE_TYPES = {
    "article", "newsarticle", "blogposting", "report", "scholarlyarticle",
    "reportagenewsarticle", "opinionnewsarticle", "analysisnewsarticle",
}
_MAX_AUTHOR_CHARS = 200


def _jsonld_objects(html: str) -> list[dict]:
    """All JSON-LD objects on the page (lists and top-level @graph flattened); invalid blocks skipped."""
    from bs4 import BeautifulSoup

    out: list[dict] = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                out.extend(g for g in graph if isinstance(g, dict))
            out.append(item)
    return out


def _types(obj: dict) -> set[str]:
    t = obj.get("@type")
    values = t if isinstance(t, list) else [t]
    return {v.lower() for v in values if isinstance(v, str)}


def _same_page(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.netloc.lower().removeprefix("www."), pa.path.rstrip("/")) == (
        pb.netloc.lower().removeprefix("www."), pb.path.rstrip("/"))


def _jsonld_authors(html: str, url: str | None) -> list[str]:
    """Authors of the page's main article object in JSON-LD, in order."""
    articles = [o for o in _jsonld_objects(html) if _types(o) & _ARTICLE_TYPES]
    if not articles:
        return []

    def ids(o: dict) -> list[str]:
        main = o.get("mainEntityOfPage")
        main_id = main.get("@id") if isinstance(main, dict) else main
        return [v for v in (o.get("url"), o.get("@id"), main_id) if isinstance(v, str)]

    main = next((o for o in articles if any(_same_page(i, url) for i in ids(o))), articles[0])
    raw = main.get("author")
    names: list[str] = []
    for a in raw if isinstance(raw, list) else [raw]:
        if isinstance(a, str):
            names.append(a)
        elif isinstance(a, dict) and isinstance(a.get("name"), str):
            names.append(a["name"])
    return names


def clean_authors(names: list[str]) -> list[str]:
    """Whitespace-normalise, drop empty/overlong values and `[[...]]` brackets, de-duplicate keeping order."""
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        if not isinstance(n, str):
            continue
        n = n.strip()
        m = re.fullmatch(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]", n)
        if m:
            n = m.group(1)
        n = " ".join(n.split())
        if not n or len(n) > _MAX_AUTHOR_CHARS or n.casefold() in seen:
            continue
        seen.add(n.casefold())
        out.append(n)
    return out


def _authors(html: str, url: str | None, meta: dict, trafilatura_author: str | None) -> list[str]:
    """First non-empty of: JSON-LD, trafilatura metadata (split on ';'), mcmetadata other.authors."""
    candidates = [
        _jsonld_authors(html, url),
        [a for a in (trafilatura_author or "").split(";")],
        list((meta.get("other") or {}).get("authors") or []),
    ]
    for names in candidates:
        cleaned = clean_authors(names)
        if cleaned:
            return cleaned
    return []


def extract(original_url: str, final_url: str, html: str, html_bytes: bytes) -> FetchedPage:
    mcmetadata, trafilatura = _extractors()
    try:
        meta = mcmetadata.extract(url=final_url, html_text=html, include_other_metadata=True)
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
    try:
        doc = trafilatura.extract_metadata(html, default_url=final_url)
        trafilatura_author = doc.author if doc else None
    except Exception:
        trafilatura_author = None
    page_url = None if final_url.startswith("file:") else final_url
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
        authors=_authors(html, page_url, meta, trafilatura_author),
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
