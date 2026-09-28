"""«Суть времени» digests (rp-digest-items change). All pages are synthetic (tests/rpfixture.py)."""

from __future__ import annotations

import pytest

from llmwiki import rpdigest
from llmwiki.errors import WikiError
from rpfixture import (BAD_DATELINE_BODY, UNASSIGNED_BODY, YEAR_BOUNDARY_BODY, article_html, digest_html)

ISSUE = "2026-09-26T08:41:00+03:00"


def parse(html: str, issue=ISSUE) -> dict:
    return rpdigest.parse_html(html.encode("utf-8"), issue)


def test_fixtures_load():
    for html in (digest_html(), digest_html(YEAR_BOUNDARY_BODY), article_html()):
        assert html.startswith("<!DOCTYPE html>")


# --- Parse a digest into items ---------------------------------------------------


def test_items_with_and_without_comments():
    r = parse(digest_html())
    one, two, three = r["items"]
    assert (one["n"], one["section"], one["place"], one["outlet"], one["date"]) == (
        1, "На фронтах", "ЗАРЕЧЬЕ", "Вестник", "2026-09-18")
    assert len(one["quote"]) == 2 and one["comment"] == ["Вообще-то, тревожный звонок для выдуманной энергетики."]
    assert (two["outlet"], two["comment"]) == ("РИА Север", None)
    assert three["section"] == "Милитарии всех стран" and three["place"] == "НЬЮ-ГОРОД"
    assert three["comment"] == ["Примечательно, что закупка совпала с выборами.", "И это не случайность."]
    assert r["problems"] == [] and r["unassigned"] == []


def test_issue_identity_from_header_not_sidebar():
    assert parse(digest_html())["issue"] == {"newspaper": "Суть времени", "number": 123, "published": ISSUE}
    assert parse(digest_html(number=None))["issue"]["number"] is None


def test_hidden_and_service_markup_ignored():
    one = parse(digest_html())["items"][0]
    text = " ".join(one["quote"] + one["comment"])
    for junk in ("служебный", "Смотрите также", "Выдуманный ролик", "Ya.Context", "боковой колонки"):
        assert junk not in text
    assert one["quote"][1] == "Директор станции Иван Выдуманов призвал к сдержанности."


def test_emphasis_kept_and_spaces_normalised():
    one = parse(digest_html())["items"][0]
    assert one["quote"][0] == "*Дрон повредил* градирню Заречной станции, сообщил выдуманный агент."
    assert one["dateline"] == "ЗАРЕЧЬЕ, 18 сентября — «Вестник»"


def test_emphasis_whitespace_outside_markers():
    body = ('<p class="block_date">ЛЕСНОЙ, 1 сентября — РИА Север</p>'
            '<p class="quote">Он сказал: <em>«Да» </em>и ушёл<em> </em>.</p>')
    assert parse(digest_html(body))["items"][0]["quote"] == ["Он сказал: *«Да»* и ушёл ."]


# --- Item dates carry the issue's year --------------------------------------------


def test_same_year():
    assert parse(digest_html())["items"][0]["date"] == "2026-09-18"


def test_year_boundary():
    items = parse(digest_html(YEAR_BOUNDARY_BODY), "2027-01-09")["items"]
    assert [i["date"] for i in items] == ["2026-12-29", "2027-01-05"]


def test_date_only_issue():
    assert parse(digest_html(), "2026-09-26")["items"][1]["date"] == "2026-09-19"


def test_unparseable_dateline():
    r = parse(digest_html(BAD_DATELINE_BODY))
    bad, good = r["items"]
    assert (bad["date"], bad["place"], bad["outlet"], bad["dateline"]) == (None, None, None, "ЗАРЕЧЬЕ — «Вестник»")
    assert good["date"] == "2026-09-19"
    assert [p["code"] for p in r["problems"]] == ["bad_dateline"] and r["problems"][0]["item"] == 1


def test_impossible_day_is_unparseable():
    body = '<p class="block_date">ЛЕСНОЙ, 31 февраля — РИА Север</p><p class="quote">x</p>'
    assert parse(digest_html(body))["items"][0]["date"] is None


def test_unknown_issue_date():
    with pytest.raises(WikiError) as e:
        parse(digest_html(), None)
    assert e.value.code == "no_issue_date"


def test_text_before_first_dateline_reported():
    r = parse(digest_html(UNASSIGNED_BODY))
    assert r["unassigned"] == [{"section": "Разное", "kind": "quote", "text": "Цитата до первой строки с датой."}]
    assert [p["code"] for p in r["problems"]] == ["unassigned_text"]
    assert r["items"][0]["quote"] == ["Обычная новость."]


# --- Refuse unknown formats --------------------------------------------------------


def test_ordinary_article_refused():
    with pytest.raises(WikiError) as e:
        parse(article_html())
    assert e.value.code == "not_rp_digest"


@pytest.mark.parametrize("dateline, place, outlet", [
    ("НЬЮ-ЙОРК, 19 сентября — РБК", "НЬЮ-ЙОРК", "РБК"),
    ("ЭР-РИЯД, 11 сентября — «Коммерсант»", "ЭР-РИЯД", "Коммерсант"),
    ("САН-ФРАНЦИСКО, 11 сентября — Yahoo News", "САН-ФРАНЦИСКО", "Yahoo News"),
    ("ЛЕСНОЙ, 1 мая — «Север» и «Юг»", "ЛЕСНОЙ", "«Север» и «Юг»"),
])
def test_dateline_grammar(dateline, place, outlet):
    import datetime as dt
    p = rpdigest.parse_dateline(dateline, dt.date(2026, 9, 26))
    assert (p["place"], p["outlet"]) == (place, outlet)


def test_capture_check():
    html = digest_html().encode()
    assert rpdigest.looks_like_digest("https://rossaprimavera.ru/article/x", html)
    assert rpdigest.looks_like_digest("https://www.rossaprimavera.ru/article/x", html)
    assert not rpdigest.looks_like_digest("https://example.org/article/x", html)
    assert not rpdigest.looks_like_digest("https://notrossaprimavera.ru/a", html)
    assert not rpdigest.looks_like_digest("https://rossaprimavera.ru/article/y", article_html().encode())
    assert not rpdigest.looks_like_digest(None, html)


# --- Capture marker ----------------------------------------------------------------

from fakeweb import FakeWeb  # noqa: E402
from llmwiki import fetch, sources  # noqa: E402
from llmwiki.pages import parse as parse_doc  # noqa: E402
from llmwiki.vault import Vault  # noqa: E402
from rpfixture import RP_URL  # noqa: E402


@pytest.fixture
def web(monkeypatch):
    fw = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", fw)
    return fw


def _raw_meta(tmp_vault, res) -> dict:
    return parse_doc((tmp_vault.root / res["path"]).read_text(encoding="utf-8")).meta


def test_digest_url_marked(tmp_vault, web):
    web.add(RP_URL, digest_html())
    res = sources.capture(Vault(tmp_vault.root), RP_URL)
    assert _raw_meta(tmp_vault, res)["format"] == "rp-digest"


def test_same_site_article_not_marked(tmp_vault, web):
    url = "https://rossaprimavera.ru/article/1111aaaa"
    web.add(url, article_html())
    assert "format" not in _raw_meta(tmp_vault, sources.capture(Vault(tmp_vault.root), url))


def test_other_domain_with_markup_not_marked(tmp_vault, web):
    url = "https://example.org/digest"
    web.add(url, digest_html().replace(RP_URL, url))
    assert "format" not in _raw_meta(tmp_vault, sources.capture(Vault(tmp_vault.root), url))


def test_saved_digest_marked(tmp_vault, tmp_path):
    f = tmp_path / "digest.html"
    f.write_text(digest_html(), encoding="utf-8")  # canonical points at rossaprimavera.ru
    assert _raw_meta(tmp_vault, sources.capture(Vault(tmp_vault.root), str(f)))["format"] == "rp-digest"


def test_text_file_not_marked(tmp_vault, tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("ЗАРЕЧЬЕ, 18 сентября — «Вестник»\nсинтетический текст", encoding="utf-8")
    assert "format" not in _raw_meta(tmp_vault, sources.capture(Vault(tmp_vault.root), str(f)))


# --- wiki source-items-rp ------------------------------------------------------------


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_cli_json(tmp_vault, web, run_cli):
    web.add(RP_URL, digest_html())
    raw = sources.capture(Vault(tmp_vault.root), RP_URL)["path"]
    before = _snapshot(tmp_vault.root)
    r = run_cli("source-items-rp", raw, "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out
    d = r.json()
    assert d["path"] == raw and d["format"] == "rp-digest"
    assert d["issue"]["number"] == 123 and d["issue"]["title"] == "Выдуманное «обострение»"
    assert [i["date"] for i in d["items"]] == ["2026-09-18", "2026-09-19", "2026-09-20"]
    assert _snapshot(tmp_vault.root) == before


def test_cli_text(tmp_vault, web, run_cli):
    web.add(RP_URL, digest_html())
    raw = sources.capture(Vault(tmp_vault.root), RP_URL)["path"]
    r = run_cli("source-items-rp", raw, "--vault", tmp_vault.root)
    assert r.code == 0
    assert "  1  2026-09-18  ЗАРЕЧЬЕ — Вестник  [comment]" in r.out
    assert "  2  2026-09-19  ЛЕСНОЙ — РИА Север\n" in r.out


def test_cli_problems_exit_1(tmp_vault, web, run_cli):
    web.add(RP_URL, digest_html(BAD_DATELINE_BODY + "<p>" + "Длинный синтетический абзац. " * 20 + "</p>"))
    raw = sources.capture(Vault(tmp_vault.root), RP_URL)["path"]
    r = run_cli("source-items-rp", raw, "--json", "--vault", tmp_vault.root)
    assert r.code == 1 and r.json()["items"][0]["date"] is None


def test_cli_issue_date_from_original(tmp_vault, run_cli):
    """A raw file without `published` falls back to the stored original's date."""
    orig = tmp_vault.root / "raw/.orig/d.html"
    orig.write_text(digest_html(), encoding="utf-8")
    raw = tmp_vault.raw("d", "тело", kind="url", original_url=RP_URL, original_file="raw/.orig/d.html")
    r = run_cli("source-items-rp", tmp_vault.rel(raw), "--json", "--vault", tmp_vault.root)
    assert r.code == 0 and r.json()["issue"]["published"].startswith("2026-09-26")


def test_cli_not_digest(tmp_vault, web, run_cli):
    url = "https://rossaprimavera.ru/article/1111aaaa"
    web.add(url, article_html())
    raw = sources.capture(Vault(tmp_vault.root), url)["path"]
    r = run_cli("source-items-rp", raw, "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "not_rp_digest"


def test_cli_text_file_no_original(tmp_vault, tmp_path, run_cli):
    f = tmp_path / "note.txt"
    f.write_text("синтетический текст", encoding="utf-8")
    raw = sources.capture(Vault(tmp_vault.root), str(f))["path"]
    r = run_cli("source-items-rp", raw, "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "no_original"


# --- Digest vault: item pages, search, timeline, lint -----------------------------------------

import datetime as _dt  # noqa: E402

from llmwiki import lint, search, timeline  # noqa: E402

HUB = "Суть времени №123"


@pytest.fixture
def digest_vault(tmp_vault, web):
    """A captured synthetic digest with a hub page and pages for all three items."""
    web.add(RP_URL, digest_html())
    raw = sources.capture(Vault(tmp_vault.root), RP_URL)["path"]
    tmp_vault.raw_rel = raw
    items = [
        ("Дрон повредил градирню (Вестник, 2026-09-18)", 1, _dt.date(2026, 9, 18), "Вестник", True,
         "## Сообщение\n> Дрон повредил градирню.\n## Комментарий редакции\n> Тревожный звонок."),
        ("Фонари в Лесном (РИА Север, 2026-09-19)", 2, _dt.date(2026, 9, 19), "РИА Север", None,
         "## Сообщение\n> Градирня тут ни при чём, фонари."),
        ("Закупка дронов (Газета.XX, 2026-09-20)", 3, _dt.date(2026, 9, 20), "Газета.XX", True,
         "## Сообщение\n> Закупка.\n## Комментарий редакции\n> Совпало с выборами."),
    ]
    links = []
    for title, n, day, outlet, comm, body in items:
        meta = {"raw": raw, "item": n, "published": day, "outlet": outlet, "via": f"[[{HUB}]]"}
        if comm:
            meta["commentary"] = True
        tmp_vault.page("source", title, body=body + f"\n\n[[{HUB}]]", summary="s", **meta)
        links.append(f"[[{title}]]")
    tmp_vault.page("source", HUB, body=" ".join(links), summary="Выпуск", raw=raw,
                   published=_dt.date(2026, 9, 26), authors=["[[Новости недели]]"])
    tmp_vault.page("entity", "Новости недели", body=f"[[{HUB}]]", summary="рубрика")
    tmp_vault.page("concept", "Градирня", body=links[0] + " " + links[1], summary="c", sources=links[:2])
    return tmp_vault


def _codes(root, code=None):
    fs = lint.check(Vault(root))
    return [f for f in fs if f.code.startswith("rp_item")] if code is None else [f for f in fs if f.code == code]


def test_complete_digest_clean(digest_vault):
    assert _codes(digest_vault.root) == []
    assert _codes(digest_vault.root, "missing_authors") == []


def test_item_missing(digest_vault):
    (digest_vault.root / "wiki/sources/Фонари в Лесном (РИА Север, 2026-09-19).md").unlink()
    fs = _codes(digest_vault.root)
    assert [(f.code, f.path, f.target) for f in fs] == [("rp_item_missing", digest_vault.raw_rel, "2")]


def _edit(root, title, old, new):
    p = root / f"wiki/sources/{title}.md"
    p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")


def test_commentary_flag_missing(digest_vault):
    _edit(digest_vault.root, "Дрон повредил градирню (Вестник, 2026-09-18)", "commentary: true\n", "")
    fs = _codes(digest_vault.root)
    assert [f.code for f in fs] == ["rp_item_mismatch"] and "commentary" in fs[0].message


def test_commentary_flag_without_comment(digest_vault):
    _edit(digest_vault.root, "Фонари в Лесном (РИА Север, 2026-09-19)", "item: 2\n", "item: 2\ncommentary: true\n")
    assert [f.code for f in _codes(digest_vault.root)] == ["rp_item_mismatch"]


def test_wrong_published(digest_vault):
    _edit(digest_vault.root, "Фонари в Лесном (РИА Север, 2026-09-19)", "2026-09-19\n", "2026-09-26\n")
    fs = _codes(digest_vault.root)
    assert [f.code for f in fs] == ["rp_item_mismatch"] and "2026-09-19" in fs[0].message


def test_item_out_of_range(digest_vault):
    _edit(digest_vault.root, "Фонари в Лесном (РИА Север, 2026-09-19)", "item: 2\n", "item: 9\n")
    assert sorted(f.code for f in _codes(digest_vault.root)) == ["rp_item_mismatch", "rp_item_missing"]


def test_unparseable_original_reported_once(digest_vault):
    orig = next((digest_vault.root / "raw/.orig").iterdir())
    orig.write_text(article_html(), encoding="utf-8")
    fs = _codes(digest_vault.root)
    assert [(f.code, f.path) for f in fs] == [("rp_item_mismatch", digest_vault.raw_rel)]


def test_pending_digest_not_checked(tmp_vault, web):
    web.add(RP_URL, digest_html())
    sources.capture(Vault(tmp_vault.root), RP_URL)
    assert _codes(tmp_vault.root) == []


@pytest.mark.parametrize("field, value", [("commentary", "yes"), ("item", 0), ("item", True), ("outlet", 5),
                                          ("via", ["[[x]]"])])
def test_wrong_field_types(tmp_vault, field, value):
    raw = tmp_vault.raw("r", "текст")
    tmp_vault.page("source", "Страница", summary="s", raw=tmp_vault.rel(raw), **{field: value})
    fs = [f for f in lint.check(Vault(tmp_vault.root)) if f.code == "frontmatter_invalid"]
    assert len(fs) == 1 and f"`{field}`" in fs[0].message


def test_valid_field_types(tmp_vault):
    raw = tmp_vault.raw("r", "текст")
    tmp_vault.page("source", "Страница", summary="s", raw=tmp_vault.rel(raw), item=3, outlet="РБК",
                   via="[[Выпуск]]", commentary=False)
    assert not [f for f in lint.check(Vault(tmp_vault.root)) if f.code == "frontmatter_invalid"]


def test_search_commentary_only(digest_vault):
    res, _ = search.search(Vault(digest_vault.root), "градирня", commentary=True)
    assert [r["title"] for r in res["results"]] == ["Дрон повредил градирню (Вестник, 2026-09-18)"]
    assert res["results"][0]["outlet"] == "Вестник" and res["commentary"] is True
    res, _ = search.search(Vault(digest_vault.root), "градирня")
    assert "Фонари в Лесном (РИА Север, 2026-09-19)" in [r["title"] for r in res["results"]]


def test_search_commentary_period_without_terms(digest_vault):
    res, _ = search.search(Vault(digest_vault.root), "", commentary=True, since="2026-09", sort="newest")
    assert [r["published"] for r in res["results"]] == ["2026-09-20", "2026-09-18"]


def test_search_commentary_raw_is_usage_error(digest_vault, run_cli):
    r = run_cli("search", "градирня", "--raw", "--commentary", "--json", "--vault", digest_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "invalid_option"


def test_search_cli_shows_outlet(digest_vault, run_cli):
    r = run_cli("search", "градирня", "--commentary", "--vault", digest_vault.root)
    assert r.code == 0 and ", Вестник)" in r.out


def test_timeline_outlet_and_item_dates(digest_vault):
    res = timeline.timeline(Vault(digest_vault.root), "Градирня")
    assert [(e["published"], e.get("outlet")) for e in res["entries"]] == [
        ("2026-09-18", "Вестник"), ("2026-09-19", "РИА Север")]


# --- Schema and workflows ---------------------------------------------------------------------


@pytest.mark.parametrize("lang", [None, "ru", "zh"])
def test_schema_covers_digests(tmp_path, run_cli, lang):
    target = tmp_path / "v"
    run_cli("init", target, "--no-git", *(["--language", lang] if lang else []))
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    for needle in ("format: rp-digest", "wiki source-items-rp", "Суть времени №<number>", "item: 7",
                   "outlet: РБК", "commentary: true", "verbatim", "По мнению редакции",
                   "Never present it as a statement of the quoted outlet", "--commentary"):
        assert needle in agents, needle


def test_workflows_cover_digests(tmp_path, run_cli):
    target = tmp_path / "v"
    run_cli("init", target, "--no-git")
    for ingest in (target / ".claude/commands/wiki-ingest.md", target / ".agents/skills/wiki-ingest/SKILL.md"):
        text = ingest.read_text(encoding="utf-8")
        for needle in ("format: rp-digest", "wiki source-items-rp <path> --json", "Суть времени №<number>",
                       "commentary: true", "verbatim", "rp_item_missing", "date: null"):
            assert needle in text, (ingest, needle)
    for query in (target / ".claude/commands/wiki-query.md", target / ".agents/skills/wiki-query/SKILL.md"):
        assert "--commentary" in query.read_text(encoding="utf-8")
