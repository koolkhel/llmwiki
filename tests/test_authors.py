"""Author tracking (track-authors change). All pages and names are synthetic."""

from __future__ import annotations

import datetime as dt
import hashlib
import json

import pytest

from fakeweb import FakeWeb
from llmwiki import fetch, sources
from llmwiki.pages import parse
from llmwiki.vault import Vault

PAGE_URL = "https://news.example.org/article/abc123"


def page(jsonld: object | None = None, meta_author: str | None = None, sidebar: str | None = None,
         byline: str | None = None, extra_head: str = "") -> str:
    head = f"<title>Синтетическая статья</title>{extra_head}"
    if jsonld is not None:
        blocks = jsonld if isinstance(jsonld, tuple) else (jsonld,)
        for b in blocks:
            text = b if isinstance(b, str) else json.dumps(b, ensure_ascii=False)
            head += f'<script type="application/ld+json">{text}</script>'
    if meta_author:
        head += f'<meta name="author" content="{meta_author}">'
    paras = "".join(
        f"<p>Синтетический абзац {i} о виджетах и шестерёнках, достаточно длинный для извлечения текста.</p>"
        for i in range(8)
    )
    by = f'<div class="meta"><a class="author" href="/authors/x">{byline}</a></div>' if byline else ""
    side = (f'<aside class="widget"><p class="widget_author"><a class="author">{sidebar}</a></p>'
            f"<p>Другая статья</p></aside>") if sidebar else ""
    return (f"<!DOCTYPE html><html><head>{head}</head><body><article><h1>Синтетическая статья</h1>{by}"
            f"{paras}</article>{side}</body></html>")


def article(authors, type_="NewsArticle", url=PAGE_URL, **extra):
    return {"@context": "https://schema.org", "@type": type_, "url": url, "author": authors, **extra}


# --- 1.1 JSON-LD ----------------------------------------------------------------


def test_jsonld_list_with_breadcrumb():
    html = page([{"@type": "BreadcrumbList"}, article([{"@type": "Person", "name": "Иван Синтетов"}])])
    assert fetch._jsonld_authors(html, PAGE_URL) == ["Иван Синтетов"]


def test_jsonld_graph_and_single_object():
    graph = {"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, article({"@type": "Person", "name": "A One"})]}
    assert fetch._jsonld_authors(page(graph), PAGE_URL) == ["A One"]
    assert fetch._jsonld_authors(page(article("Plain String Author")), PAGE_URL) == ["Plain String Author"]


def test_jsonld_organization_and_order():
    authors = [{"@type": "Person", "name": "Anna A"}, {"@type": "Organization", "name": "Synthetic Desk"},
               {"@type": "Person", "name": "Boris B"}]
    assert fetch._jsonld_authors(page(article(authors)), PAGE_URL) == ["Anna A", "Synthetic Desk", "Boris B"]


def test_jsonld_prefers_article_matching_page_url():
    other = article({"@type": "Person", "name": "Wrong Person"}, url="https://news.example.org/article/other")
    mine = article({"@type": "Person", "name": "Right Person"}, url=PAGE_URL + "#body")
    assert fetch._jsonld_authors(page((other, mine)), PAGE_URL) == ["Right Person"]


def test_jsonld_type_list_and_main_entity():
    obj = {"@type": ["CreativeWork", "BlogPosting"], "mainEntityOfPage": {"@id": PAGE_URL},
           "author": {"name": "Listed Type"}}
    assert fetch._jsonld_authors(page(obj), PAGE_URL) == ["Listed Type"]


def test_jsonld_invalid_block_skipped_and_breadcrumb_only():
    html = page(("{not json", article({"@type": "Person", "name": "After Invalid"})))
    assert fetch._jsonld_authors(html, PAGE_URL) == ["After Invalid"]
    assert fetch._jsonld_authors(page({"@type": "BreadcrumbList"}), PAGE_URL) == []


# --- 1.2 precedence, cleaning, FetchedPage ------------------------------------------


def _extract(html: str):
    return fetch.extract(PAGE_URL, PAGE_URL, html, html.encode())


def test_sidebar_trap_only_article_author():
    html = page(article([{"@type": "Person", "name": "Владимир Синтетов"}]),
                byline="Владимир Синтетов", sidebar="Максим Другой, Владимир Синтетов")
    assert _extract(html).authors == ["Владимир Синтетов"]


def test_meta_tag_fallback():
    assert _extract(page(meta_author="Jane Doe")).authors == ["Jane Doe"]


def test_trafilatura_semicolon_split():
    assert fetch._authors("<html></html>", None, {}, "Anna A; Boris B") == ["Anna A", "Boris B"]
    assert fetch._authors("<html></html>", None, {}, "Doe, Jane") == ["Doe, Jane"]  # comma kept


def test_mcmetadata_last_resort():
    assert fetch._authors("<html></html>", None, {"other": {"authors": ["From Newspaper"]}}, None) == ["From Newspaper"]


def test_first_source_wins_no_merge():
    html = page(article({"@type": "Person", "name": "From JSON-LD"}))
    assert fetch._authors(html, PAGE_URL, {"other": {"authors": ["Other Spelling"]}}, "Trafilatura Name") == ["From JSON-LD"]


@pytest.mark.parametrize(
    "names, expected",
    [
        (["  Anna   A ", "anna a", "Boris B"], ["Anna A", "Boris B"]),
        (["[[Jane Doe]]", "[[John Roe|J. Roe]]"], ["Jane Doe", "John Roe"]),
        (["", "   ", "x" * 201, None, 5], []),
    ],
)
def test_clean_authors(names, expected):
    assert fetch.clean_authors(names) == expected


def test_no_author_anywhere():
    assert _extract(page()).authors == []


# --- 2.1 capture writes authors -------------------------------------------------------

NOW = dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.timezone.utc)
KOLDIN_LIKE = page(article([{"@type": "Person", "name": "Владимир Синтетов"}]),
                   byline="Владимир Синтетов", sidebar="Максим Другой, Владимир Синтетов")


@pytest.fixture
def vault(tmp_vault):
    return Vault(tmp_vault.root)


def _raw_meta(vault, res):
    return parse((vault.root / res["path"]).read_text(encoding="utf-8")).meta


def test_url_capture_records_authors(vault, monkeypatch):
    web = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", web)
    web.add(PAGE_URL, KOLDIN_LIKE)
    m = _raw_meta(vault, sources.capture(vault, PAGE_URL, now=NOW))
    assert m["authors"] == ["Владимир Синтетов"]
    assert list(m)[:3] == ["kind", "title", "authors"]


def test_saved_page_records_authors(vault, tmp_path):
    f = tmp_path / "saved.html"
    f.write_text(page(article(["Anna A", "Boris B"]), extra_head=f'<link rel="canonical" href="{PAGE_URL}">'))
    m = _raw_meta(vault, sources.capture(vault, str(f), now=NOW))
    assert m["authors"] == ["Anna A", "Boris B"] and m["kind"] == "url"


def test_saved_page_without_url_records_authors(vault, tmp_path):
    f = tmp_path / "saved.html"
    f.write_text(page(meta_author="Jane Doe"))
    m = _raw_meta(vault, sources.capture(vault, str(f), now=NOW))
    assert m["kind"] == "file" and m["authors"] == ["Jane Doe"]


@pytest.mark.parametrize(
    "fm, expected",
    [
        ('author: "[[Jane Doe]]"', ["Jane Doe"]),
        ("author:\n  - Jane Doe\n  - John Roe", ["Jane Doe", "John Roe"]),
        ('authors: ["[[A Person]]", "B Person"]', ["A Person", "B Person"]),
    ],
)
def test_md_frontmatter_authors(vault, tmp_path, fm, expected):
    f = tmp_path / "clip.md"
    f.write_text(f"---\ntitle: Clip\n{fm}\n---\n# Clip\n\nsynthetic body {fm}\n")
    m = _raw_meta(vault, sources.capture(vault, str(f), now=NOW))
    assert m["authors"] == expected and list(m)[:3] == ["kind", "title", "authors"]


def test_txt_and_authorless_have_no_key(vault, tmp_path, monkeypatch):
    (tmp_path / "n.txt").write_text("synthetic text by nobody in particular")
    assert "authors" not in _raw_meta(vault, sources.capture(vault, str(tmp_path / "n.txt"), now=NOW))
    web = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", web)
    web.add(PAGE_URL, page())
    assert "authors" not in _raw_meta(vault, sources.capture(vault, PAGE_URL, now=NOW))


# --- 3.1 source-meta backfill ---------------------------------------------------------



def _old_style_capture(tmp_vault, name: str, html: str, source_page_authors=None, ingest=True):
    """A raw file as captured before authors were recorded, plus its .orig HTML (and a source page)."""
    orig = tmp_vault.root / "raw" / ".orig" / f"{name}.html"
    orig.write_text(html, encoding="utf-8")
    raw = tmp_vault.raw(name, "synthetic body text of an older capture", kind="url",
                        original_url=PAGE_URL, original_file=f"raw/.orig/{name}.html")
    if ingest:
        extra = {"authors": source_page_authors} if source_page_authors is not None else {}
        tmp_vault.page("source", name, summary="s", raw=tmp_vault.rel(raw), **extra)
    return raw


def _snapshot(root):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def test_source_meta_all_lists_old_capture(run_cli, tmp_vault):
    _old_style_capture(tmp_vault, "2026-01-01-Old", KOLDIN_LIKE)
    _old_style_capture(tmp_vault, "2026-01-02-Done", KOLDIN_LIKE, source_page_authors=["[[Владимир Синтетов]]"])
    _old_style_capture(tmp_vault, "2026-01-03-Pending", KOLDIN_LIKE, ingest=False)
    before = _snapshot(tmp_vault.root)
    r = run_cli("source-meta", "--all", "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out
    items = {i["raw"]: i for i in r.json()["items"]}
    assert set(items) == {"raw/2026-01-01-Old.md", "raw/2026-01-03-Pending.md"}
    assert items["raw/2026-01-01-Old.md"] == {"raw": "raw/2026-01-01-Old.md", "source_page": "wiki/sources/2026-01-01-Old.md",
                                             "missing": ["authors"], "authors": ["Владимир Синтетов"], "published": None}
    assert items["raw/2026-01-03-Pending.md"]["source_page"] is None
    assert _snapshot(tmp_vault.root) == before


def test_source_meta_recorded_authors_used_without_extraction(run_cli, tmp_vault, monkeypatch):
    tmp_vault.raw("2026-01-04-New", "body", authors=["Anna A"])
    tmp_vault.page("source", "2026-01-04-New", summary="s", raw="raw/2026-01-04-New.md")
    monkeypatch.setattr(sources, "derive_meta", lambda *a: pytest.fail("should not re-extract"))
    items = run_cli("source-meta", "--all", "--json", "--vault", tmp_vault.root).json()["items"]
    assert items == [{"raw": "raw/2026-01-04-New.md", "source_page": "wiki/sources/2026-01-04-New.md",
                      "missing": ["authors"], "authors": ["Anna A"], "published": None}]


def test_source_meta_single(run_cli, tmp_vault):
    raw = _old_style_capture(tmp_vault, "2026-01-01-Old", KOLDIN_LIKE)
    doc = run_cli("source-meta", tmp_vault.rel(raw), "--json", "--vault", tmp_vault.root).json()
    assert doc["derivable"] is True and doc["derived"]["authors"] == ["Владимир Синтетов"]
    assert doc["recorded"]["authors"] is None and doc["source_page"] == "wiki/sources/2026-01-01-Old.md"


def test_source_meta_txt_not_derivable(run_cli, tmp_vault):
    raw = tmp_vault.raw("2026-01-05-Txt", "plain text")
    doc = run_cli("source-meta", tmp_vault.rel(raw), "--json", "--vault", tmp_vault.root).json()
    assert doc["derivable"] is False and doc["derived"] is None


def test_source_meta_usage(run_cli, tmp_vault):
    assert run_cli("source-meta", "--vault", tmp_vault.root).code == 2
    assert run_cli("source-meta", "raw/x.md", "--all", "--vault", tmp_vault.root).code == 2


# --- 5.1 search --author ---------------------------------------------------------------


@pytest.fixture
def authored(tmp_vault):
    tmp_vault.page("source", "Про инвестиции", body="Инвестиции в ИИ растут.", summary="a",
                   raw="raw/a.md", authors=["[[Владимир Синтетов]]"])
    tmp_vault.page("source", "Про рынки", body="Рынки и шестерёнки.", summary="b",
                   raw="raw/b.md", authors=["[[Владимир Синтетов|В. Синтетов]]", "[[Anna A]]"])
    tmp_vault.page("source", "Чужая статья", body="Инвестиции тоже.", summary="c",
                   raw="raw/c.md", authors=["[[Максим Другой]]"])
    tmp_vault.page("entity", "Владимир Синтетов", body="Автор.", summary="person", tags=["person"])
    return tmp_vault


def _s(run_cli, v, *args):
    r = run_cli("search", *args, "--json", "--vault", v.root)
    assert r.code == 0, r.out + r.err
    return r.json()


def test_search_by_author_only(run_cli, authored):
    res = _s(run_cli, authored, "--author", "Владимир Синтетов")
    assert [x["title"] for x in res["results"]] == ["Про инвестиции", "Про рынки"]  # by title; entity page excluded
    assert res["author"] == "Владимир Синтетов" and {x["match"] for x in res["results"]} == {"exact"}


def test_declined_author_name(run_cli, authored):
    res = _s(run_cli, authored, "--author", "Синтетова")
    assert [x["title"] for x in res["results"]] == ["Про инвестиции", "Про рынки"]
    assert {x["match"] for x in res["results"]} == {"lemma"}
    assert _s(run_cli, authored, "--author", "Синтетова", "--exact")["results"] == []


def test_author_combined_with_terms(run_cli, authored):
    res = _s(run_cli, authored, "инвестиции", "--author", "Синтетов")
    assert [x["title"] for x in res["results"]] == ["Про инвестиции"]


def test_all_author_words_must_match_one_name(run_cli, authored):
    # "Anna" and "Синтетов" are both authors of "Про рынки", but not one person.
    assert _s(run_cli, authored, "--author", "Anna Синтетов")["results"] == []
    assert [x["title"] for x in _s(run_cli, authored, "--author", "anna")["results"]] == ["Про рынки"]


def test_raw_by_author(run_cli, tmp_vault):
    tmp_vault.raw("2026-01-01-A", "синтетический текст", authors=["Владимир Синтетов"])
    tmp_vault.raw("2026-01-01-B", "другой текст")
    res = _s(run_cli, tmp_vault, "--author", "Синтетова", "--raw")
    assert [x["path"] for x in res["results"]] == ["raw/2026-01-01-A.md"]


def test_empty_query_still_rejected(run_cli, tmp_vault):
    r = run_cli("search", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "empty_query"
    r = run_cli("search", "--author", "  ", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "empty_query"


@pytest.mark.parametrize("query", ["Колдина", "Колдиным", "Пупкина", "Шестерёнкину", "Синтетовым"])
def test_declined_surnames_real_and_unknown(run_cli, tmp_vault, query):
    base = {"Колдина": "Колдин", "Колдиным": "Колдин", "Пупкина": "Пупкин", "Шестерёнкину": "Шестерёнкин",
            "Синтетовым": "Синтетов"}[query]
    tmp_vault.page("source", "Статья", body="текст", summary="s", raw="raw/s.md", authors=[f"[[Иван {base}]]"])
    assert [x["title"] for x in _s(run_cli, tmp_vault, "--author", query)["results"]] == ["Статья"]
