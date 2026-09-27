"""Publication dates (track-publication-dates change). All pages are synthetic."""

from __future__ import annotations

import datetime as dt
import hashlib
import json

import pytest

from fakeweb import FakeWeb
from llmwiki import fetch, sources
from llmwiki.pages import parse
from llmwiki.vault import Vault

URL = "https://news.example.org/article/d1"


def page(jsonld: dict | None = None, head: str = "", body_extra: str = "", article_extra: str = "") -> str:
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    paras = "".join(f"<p>Synthetic paragraph {i} about gizmos, long enough for extraction to keep it.</p>"
                    for i in range(8))
    return (f"<html><head><title>Synthetic</title>{ld}{head}</head><body>{body_extra}"
            f"<article><h1>Synthetic</h1>{article_extra}{paras}</article></body></html>")


def art(**kw):
    return {"@type": "NewsArticle", "url": URL, **kw}


# --- 1.1 parsing ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-04-09T06:25+03:00", "2026-04-09T06:25:00+03:00"),
        ("2026-04-09T03:25:40Z", "2026-04-09T03:25:40+00:00"),
        ("2026-04-09T06:25:00.123+03:00", "2026-04-09T06:25:00+03:00"),
        ("2026-04-09T06:25", "2026-04-09T06:25:00"),
        ("2026-04-09", "2026-04-09"),
        (dt.date(2026, 3, 1), "2026-03-01"),
    ],
)
def test_parse_and_format(value, expected):
    assert fetch.format_date(fetch.parse_date(value)) == expected


@pytest.mark.parametrize("value", ["2026", "2026-04", "April 9, 2026", "", None, 5, "1850-01-01", "2999-01-01",
                                   "2026-13-40", "not a date"])
def test_parse_rejects(value):
    assert fetch.parse_date(value) is None


# --- 1.1 precedence -----------------------------------------------------------------------------


def dates(html, meta=None):
    return fetch._dates(html, URL, meta or {})


def test_jsonld_with_offset_and_modified():
    html = page(art(datePublished="2026-04-09T06:25+03:00", dateModified="2026-04-14T01:00+03:00"))
    assert dates(html) == ("2026-04-09T06:25:00+03:00", "2026-04-14T01:00:00+03:00", "jsonld")


def test_date_only_meta():
    html = page(head='<meta property="article:published_time" content="2026-04-09">')
    assert dates(html) == ("2026-04-09", None, "meta")


def test_modified_from_meta_even_when_published_from_meta():
    html = page(head='<meta property="article:published_time" content="2026-04-09T10:00Z">'
                     '<meta property="article:modified_time" content="2026-05-01T12:00Z">')
    assert dates(html) == ("2026-04-09T10:00:00+00:00", "2026-05-01T12:00:00+00:00", "meta")


def test_time_inside_article_preferred():
    html = page(body_extra='<header><time datetime="2020-01-01">old nav date</time></header>',
                article_extra='<time datetime="2026-04-09T06:25+03:00">9 April</time>')
    assert dates(html)[0::2] == ("2026-04-09T06:25:00+03:00", "time")


def test_jsonld_beats_conflicting_heuristic():
    html = page(art(datePublished="2026-04-09"))
    assert dates(html, {"publication_date": dt.datetime(2002, 2, 25)}) == ("2026-04-09", None, "jsonld")


def test_heuristic_is_a_plain_date():
    assert dates(page(), {"publication_date": dt.datetime(2026, 8, 2, 0, 0)}) == ("2026-08-02", None, "heuristic")


def test_junk_skipped_for_next_source():
    html = page(art(datePublished="sometime"), head='<meta property="article:published_time" content="2026-04-09">')
    assert dates(html) == ("2026-04-09", None, "meta")


def test_no_dates():
    assert dates(page()) == (None, None, None)


def test_fetched_page_carries_dates():
    html = page(art(datePublished="2026-04-09T06:25+03:00", dateModified="2026-04-14T01:00+03:00"))
    p = fetch.extract(URL, URL, html, html.encode())
    assert (p.published, p.modified, p.published_via) == (
        "2026-04-09T06:25:00+03:00", "2026-04-14T01:00:00+03:00", "jsonld")


# --- 1.2 capture writes dates -----------------------------------------------------------------

NOW = dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.timezone.utc)
DATED = page(art(datePublished="2026-04-09T06:25+03:00", dateModified="2026-04-14T01:00+03:00",
                 author={"@type": "Person", "name": "Анатолий Синтетов"}))


@pytest.fixture
def vault(tmp_vault):
    return Vault(tmp_vault.root)


def _meta(vault, res):
    return parse((vault.root / res["path"]).read_text(encoding="utf-8")).meta


def test_url_capture_dates(vault, monkeypatch):
    web = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", web)
    web.add(URL, DATED)
    m = _meta(vault, sources.capture(vault, URL, now=NOW))
    assert m["published"] == "2026-04-09T06:25:00+03:00" and m["modified"] == "2026-04-14T01:00:00+03:00"
    assert m["published_via"] == "jsonld"
    keys = list(m)
    assert keys.index("published") == keys.index("authors") + 1


@pytest.mark.parametrize("canonical", [True, False])
def test_saved_page_dates(vault, tmp_path, canonical):
    extra = f'<link rel="canonical" href="{URL}">' if canonical else ""
    f = tmp_path / "saved.html"
    f.write_text(DATED.replace("<head>", f"<head>{extra}"), encoding="utf-8")
    m = _meta(vault, sources.capture(vault, str(f), now=NOW))
    assert m["kind"] == ("url" if canonical else "file")
    assert m["published"] == "2026-04-09T06:25:00+03:00" and m["published_via"] == "jsonld"


@pytest.mark.parametrize("fm, expected", [("published: 2026-03-01", "2026-03-01"),
                                          ("date: '2026-03-02T10:00:00Z'", "2026-03-02T10:00:00+00:00"),
                                          ("published: soon", None)])
def test_md_frontmatter_published(vault, tmp_path, fm, expected):
    f = tmp_path / "clip.md"
    f.write_text(f"---\ntitle: Clip\n{fm}\n---\n# Clip\n\nsynthetic body for {fm}\n")
    m = _meta(vault, sources.capture(vault, str(f), now=NOW))
    assert m.get("published") == expected
    assert m.get("published_via") == ("frontmatter" if expected else None)


def test_no_date_no_keys(vault, monkeypatch, tmp_path):
    web = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", web)
    web.add(URL, page())
    m = _meta(vault, sources.capture(vault, URL, now=NOW))
    assert not {"published", "published_via", "modified"} & set(m)
    (tmp_path / "n.txt").write_text("synthetic plain text")
    assert "published" not in _meta(vault, sources.capture(vault, str(tmp_path / "n.txt"), now=NOW))


# --- 2.1 backfill report ------------------------------------------------------------------------


def test_backfill_missing_date(run_cli, tmp_vault):
    orig = tmp_vault.root / "raw" / ".orig" / "2026-04-01-Old.html"
    orig.write_text(DATED, encoding="utf-8")
    raw = tmp_vault.raw("2026-04-01-Old", "synthetic older capture body", kind="url", original_url=URL,
                        original_file="raw/.orig/2026-04-01-Old.html", published="2026-04-09T00:00:00",
                        authors=["Анатолий Синтетов"])
    tmp_vault.page("source", "Old", summary="s", raw=tmp_vault.rel(raw), authors=["[[Анатолий Синтетов]]"])
    items = run_cli("source-meta", "--all", "--json", "--vault", tmp_vault.root).json()["items"]
    assert items == [{"raw": tmp_vault.rel(raw), "source_page": "wiki/sources/Old.md", "missing": ["published"],
                      "authors": ["Анатолий Синтетов"], "published": "2026-04-09T06:25:00+03:00"}]  # re-derived wins
    one = run_cli("source-meta", tmp_vault.rel(raw), "--json", "--vault", tmp_vault.root).json()
    assert one["derived"]["modified"] == "2026-04-14T01:00:00+03:00" and one["derived"]["published_via"] == "jsonld"
    assert "published: 2026-04-09T06:25:00+03:00" in run_cli("source-meta", "--all", "--vault", tmp_vault.root).out


def test_backfill_both_missing_and_dated_page_skipped(run_cli, tmp_vault):
    raw = tmp_vault.raw("2026-04-02-Rec", "another synthetic body", published="2026-04-02", authors=["A B"])
    tmp_vault.page("source", "Rec", summary="s", raw=tmp_vault.rel(raw))
    raw2 = tmp_vault.raw("2026-04-03-Done", "a third synthetic body", published="2026-04-03", authors=["A B"])
    tmp_vault.page("source", "Done", summary="s", raw=tmp_vault.rel(raw2), authors=["[[A B]]"],
                   published=dt.date(2026, 4, 3))
    items = run_cli("source-meta", "--all", "--json", "--vault", tmp_vault.root).json()["items"]
    assert [(i["raw"], i["missing"]) for i in items] == [(tmp_vault.rel(raw), ["authors", "published"])]


# --- 3.1 search by date ----------------------------------------------------------------------


@pytest.fixture
def dated(tmp_vault):
    tmp_vault.page("source", "January", summary="a", raw="raw/a.md", published=dt.date(2026, 1, 15), body="ИИ растёт")
    tmp_vault.page("source", "April", summary="b", raw="raw/b.md", published="2026-04-09", body="ИИ и рынки")
    tmp_vault.page("source", "August", summary="c", raw="raw/c.md", published=dt.date(2026, 8, 2), body="ИИ снова")
    tmp_vault.page("source", "Undated", summary="d", raw="raw/d.md", body="ИИ без даты")
    return tmp_vault


def _titles(run_cli, v, *args):
    r = run_cli("search", *args, "--json", "--vault", v.root)
    assert r.code == 0, r.out
    return [x["title"] for x in r.json()["results"]]


def test_filter_by_period(run_cli, dated):
    assert _titles(run_cli, dated, "--since", "2026-04", "--until", "2026-06") == ["April"]
    assert _titles(run_cli, dated, "--since", "2026-04-10") == ["August"]
    assert _titles(run_cli, dated, "--until", "2026") == ["April", "August", "January"]  # by title, undated excluded


def test_chronological_order(run_cli, dated):
    assert _titles(run_cli, dated, "ИИ", "--sort", "oldest") == ["January", "April", "August", "Undated"]
    assert _titles(run_cli, dated, "ИИ", "--sort", "newest") == ["August", "April", "January", "Undated"]
    res = run_cli("search", "--sort", "oldest", "--json", "--vault", dated.root).json()["results"]
    assert res[0]["published"] == "2026-01-15" and "published" not in res[-1]


@pytest.mark.parametrize("bad", ["2026-13", "20260409", "yesterday", "2026-02-30"])
def test_invalid_date(run_cli, dated, bad):
    r = run_cli("search", "--since", bad, "--json", "--vault", dated.root)
    assert r.code == 2 and r.json()["error"]["code"] == "invalid_date"


def test_raw_filtering_uses_precise_value(run_cli, tmp_vault):
    tmp_vault.raw("2026-04-09-A", "synthetic a", published="2026-04-09T06:25:00+03:00")
    tmp_vault.raw("2026-08-02-B", "synthetic b", published="2026-08-02")
    tmp_vault.raw("2026-01-01-C", "synthetic c")
    r = run_cli("search", "--since", "2026-05", "--raw", "--json", "--vault", tmp_vault.root).json()
    assert [x["path"] for x in r["results"]] == ["raw/2026-08-02-B.md"]
    r = run_cli("search", "--sort", "oldest", "--raw", "--json", "--vault", tmp_vault.root).json()
    assert [x.get("published") for x in r["results"]] == ["2026-04-09T06:25:00+03:00", "2026-08-02", None]


def test_text_output_shows_date(run_cli, dated):
    assert "2026-04-09  [[April]]" in run_cli("search", "--since", "2026-04", "--until", "2026-04",
                                              "--vault", dated.root).out


# --- 3.2 timeline ----------------------------------------------------------------------------------



@pytest.fixture
def chrono(tmp_vault):
    v = tmp_vault
    ra = v.raw("2026-08-02-Aug", "synthetic august", published="2026-08-02")
    rb = v.raw("2026-01-15-Jan", "synthetic january", published="2026-01-15")
    rc = v.raw("2026-04-09-Morning", "synthetic morning", published="2026-04-09T06:25:00+03:00")
    rd = v.raw("2026-04-09-Evening", "synthetic evening", published="2026-04-09T18:00:00+03:00")
    v.page("concept", "Large language model", summary="LLMs", sources=["[[Undated note]]"])
    v.page("entity", "Анатолий Синтетов", summary="person", tags=["person"])
    v.page("source", "Aug", summary="August view", raw=v.rel(ra), published=dt.date(2026, 8, 2),
           body="On [[Large language model]].")
    v.page("source", "Jan", summary="January view", raw=v.rel(rb), published=dt.date(2026, 1, 15),
           body="Early take on [[large language model]].", authors=["[[Анатолий Синтетов]]"])
    v.page("source", "Evening", summary="evening", raw=v.rel(rd), published=dt.date(2026, 4, 9),
           authors=["[[Анатолий Синтетов]]"])
    v.page("source", "Morning", summary="morning", raw=v.rel(rc), published=dt.date(2026, 4, 9),
           authors=["[[Анатолий Синтетов]]"])
    v.page("source", "Undated note", summary="no date", raw="raw/none.md")
    v.page("source", "Unrelated", summary="x", raw="raw/x.md", published=dt.date(2026, 2, 1))
    return v


def _tl(run_cli, v, *args):
    r = run_cli("timeline", *args, "--json", "--vault", v.root)
    assert r.code == 0, r.out
    return r.json()


def test_concept_timeline(run_cli, chrono):
    res = _tl(run_cli, chrono, "Large language model")
    assert [(e["title"], e["published"]) for e in res["entries"]] == [
        ("Jan", "2026-01-15"), ("Aug", "2026-08-02"), ("Undated note", None)]
    assert res["entries"][-1]["undated"] is True and res["counts"] == {"total": 3, "dated": 2, "undated": 1}
    assert res["entries"][0]["authors"] == ["Анатолий Синтетов"]


def test_person_timeline_and_same_day_precision(run_cli, chrono):
    res = _tl(run_cli, chrono, "Анатолий Синтетов")
    assert [e["title"] for e in res["entries"]] == ["Jan", "Morning", "Evening"]
    assert res["entries"][1]["published"] == "2026-04-09T06:25:00+03:00"


def test_timeline_by_author_name_since(run_cli, chrono):
    res = _tl(run_cli, chrono, "--author", "Синтетова", "--since", "2026-04")
    assert [e["title"] for e in res["entries"]] == ["Morning", "Evening"]


def test_timeline_by_path_and_text(run_cli, chrono):
    assert _tl(run_cli, chrono, "wiki/concepts/Large language model.md")["counts"]["total"] == 3
    out = run_cli("timeline", "Large language model", "--vault", chrono.root).out
    assert "2026-01-15  [[Jan]]  (Анатолий Синтетов)  January view" in out and "undated" in out


def test_timeline_errors(run_cli, chrono):
    r = run_cli("timeline", "No such page", "--json", "--vault", chrono.root)
    assert r.code == 2 and r.json()["error"]["code"] == "page_not_found"
    assert run_cli("timeline", "--vault", chrono.root).code == 2
    assert run_cli("timeline", "X", "--author", "Y", "--vault", chrono.root).code == 2
    assert run_cli("timeline", "--author", "Y", "--since", "2026-99", "--vault", chrono.root).code == 2


def test_timeline_read_only(run_cli, chrono):
    snap = lambda: {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in chrono.root.rglob("*")
                    if p.is_file() and ".llmwiki" not in p.parts}
    before = snap()
    run_cli("timeline", "Large language model", "--vault", chrono.root)
    run_cli("timeline", "--author", "Синтетов", "--vault", chrono.root)
    assert snap() == before
