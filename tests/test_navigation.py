import datetime as dt
import re
import subprocess

import pytest

from conftest import CYRILLIC_TITLE, NFC_TITLE
from fakeweb import FakeWeb, article_html
from llmwiki import fetch, log
from llmwiki.index import NOTICE
from llmwiki.vault import Vault

# --- index -------------------------------------------------------------------


def test_index_content_and_order(run_cli, tmp_vault):
    tmp_vault.page("concept", "beta", summary="Short description")
    tmp_vault.page("concept", "Alpha")
    tmp_vault.page("entity", CYRILLIC_TITLE, summary="multi\nline  summary")
    tmp_vault.page("source", "Src", raw="raw/x.md")
    r = run_cli("index", "--json", "--vault", tmp_vault.root)
    assert r.code == 0 and r.json()["changed"] is True and r.json()["pages"] == 4
    text = (tmp_vault.root / "index.md").read_text()
    assert text.startswith(NOTICE)
    headings = re.findall(r"^## (\w+)", text, re.M)
    assert headings == ["Sources", "Entities", "Concepts", "Analyses"]
    concepts = text.split("## Concepts")[1].split("## Analyses")[0]
    assert concepts.strip().splitlines() == ["- [[Alpha]]", "- [[beta]] — Short description"]
    assert f"- [[{CYRILLIC_TITLE}]] — multi line summary" in text
    assert "## Analyses\n\n_None yet._\n" in text


def test_index_rerun_is_byte_identical(run_cli, tmp_vault):
    tmp_vault.page("concept", NFC_TITLE, summary="s")
    run_cli("index", "--vault", tmp_vault.root)
    first = (tmp_vault.root / "index.md").read_bytes()
    r = run_cli("index", "--json", "--vault", tmp_vault.root)
    assert r.json()["changed"] is False
    assert (tmp_vault.root / "index.md").read_bytes() == first


def test_index_pages_outside_type_folders(run_cli, tmp_vault):
    tmp_vault.page("concept", "Loose", folder="")
    run_cli("index", "--vault", tmp_vault.root)
    assert "## Other\n\n- [[Loose]]" in (tmp_vault.root / "index.md").read_text()


# --- log ---------------------------------------------------------------------


def test_log_appends_greppable_entries(run_cli, tmp_vault):
    logp = tmp_vault.root / "log.md"
    original = logp.read_text()
    v = Vault(tmp_vault.root)
    for h in (9, 12, 17):
        log.append(v, "ingest", "Some Article", now=dt.datetime(2026, 9, 27, h, 5))
    text = logp.read_text()
    assert text.startswith(original)
    out = subprocess.run(["grep", r"^## \[", str(logp)], capture_output=True, text=True).stdout.splitlines()
    assert out == [f"## [2026-09-27 {h:02d}:05] ingest | Some Article" for h in (9, 12, 17)]


def test_log_cli_with_detail(run_cli, tmp_vault):
    r = run_cli("log", "query", "What is X?", "--detail", "Filed as [[X analysis]].", "--json", "--vault", tmp_vault.root)
    assert r.code == 0
    assert re.fullmatch(r"## \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] query \| What is X\?", r.json()["entry"])
    assert (tmp_vault.root / "log.md").read_text().endswith("\n\nFiled as [[X analysis]].\n")


def test_log_file_without_trailing_newline(tmp_vault):
    logp = tmp_vault.root / "log.md"
    logp.write_text("# Log")
    log.append(Vault(tmp_vault.root), "note", "x", now=dt.datetime(2026, 1, 1, 0, 0))
    assert logp.read_text() == "# Log\n\n## [2026-01-01 00:00] note | x\n"


def test_log_unknown_operation(run_cli, tmp_vault):
    before = (tmp_vault.root / "log.md").read_bytes()
    r = run_cli("log", "deploy", "x", "--json", "--vault", tmp_vault.root)
    assert r.code == 2 and r.json()["error"]["code"] == "usage_error"
    assert (tmp_vault.root / "log.md").read_bytes() == before


# --- search ------------------------------------------------------------------


def _search(run_cli, tmp_vault, *args):
    r = run_cli("search", *args, "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out
    return r.json()


def test_title_outranks_summary_outranks_body(run_cli, tmp_vault):
    tmp_vault.page("concept", "Body Only", body="mentions sprocket here")
    tmp_vault.page("concept", "Sprocket Design")
    tmp_vault.page("entity", "Summary Only", summary="about a sprocket")
    res = _search(run_cli, tmp_vault, "sprocket")
    assert [r["title"] for r in res["results"]] == ["Sprocket Design", "Summary Only", "Body Only"]
    assert res["results"][0]["link"] == "[[Sprocket Design]]"
    assert "sprocket" in res["results"][2]["snippet"]


def test_all_terms_must_match(run_cli, tmp_vault):
    tmp_vault.page("concept", "A", body="widget gizmo")
    tmp_vault.page("concept", "B", body="widget only")
    assert [r["title"] for r in _search(run_cli, tmp_vault, "widget", "gizmo")["results"]] == ["A"]


def test_accent_and_case_insensitive(run_cli, tmp_vault):
    tmp_vault.page("concept", "Café culture")
    tmp_vault.page("concept", "Other", body="STRASSE and ÉCOLE")
    assert [r["title"] for r in _search(run_cli, tmp_vault, "cafe")["results"]] == ["Café culture"]
    assert [r["title"] for r in _search(run_cli, tmp_vault, "école", "straße")["results"]] == ["Other"]


def test_snippet_maps_back_to_original_text(run_cli, tmp_vault):
    tmp_vault.page("concept", "S", body="x" * 200 + " Ärger über Lärm " + "y" * 200)
    snip = _search(run_cli, tmp_vault, "uber")["results"][0]["snippet"]
    assert "über" in snip and snip.startswith("…") and snip.endswith("…")


def test_type_filter_and_limit(run_cli, tmp_vault):
    for i in range(5):
        tmp_vault.page("concept", f"Widget {i}")
    tmp_vault.page("entity", "Widget Corp")
    assert {r["type"] for r in _search(run_cli, tmp_vault, "widget", "--type", "entity")["results"]} == {"entity"}
    res = _search(run_cli, tmp_vault, "widget", "--limit", "2")
    assert len(res["results"]) == 2 and res["total"] == 6


def test_raw_mode(run_cli, tmp_vault):
    tmp_vault.raw("2026-01-01-Clip", "the raw text mentions flux capacitor")
    tmp_vault.page("concept", "Flux", body="flux capacitor")
    res = _search(run_cli, tmp_vault, "capacitor", "--raw")
    assert [r["path"] for r in res["results"]] == ["raw/2026-01-01-Clip.md"]
    assert res["results"][0]["type"] == "raw"


def test_search_ignores_frontmatter_body_split(run_cli, tmp_vault):
    tmp_vault.page("concept", "Tagged", tags=["zeppelin"])
    assert [r["title"] for r in _search(run_cli, tmp_vault, "zeppelin")["results"]] == ["Tagged"]


# --- status ------------------------------------------------------------------


@pytest.fixture
def web(monkeypatch):
    fw = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", fw)
    return fw


def test_status_after_capture(run_cli, web, tmp_vault):
    web.add("https://example.org/a", article_html("Pending One"))
    cap = run_cli("add-source", "https://example.org/a", "--json", "--vault", tmp_vault.root).json()
    tmp_vault.page("concept", "C")
    log.append(Vault(tmp_vault.root), "note", "hello", now=dt.datetime(2026, 1, 2, 3, 4))
    s = run_cli("status", "--json", "--vault", tmp_vault.root).json()
    assert s["raw"] == {"total": 1, "ingested": 0, "pending": 1}
    assert s["pending"] == [{"path": cap["path"], "title": "Pending One", "captured_at": s["pending"][0]["captured_at"]}]
    assert s["pages"] == {"source": 0, "entity": 0, "concept": 1, "analysis": 0}
    assert s["index_stale"] is True
    assert s["last_log"] == "## [2026-01-02 03:04] note | hello"

    tmp_vault.page("source", "Pending One", raw=cap["path"])
    run_cli("index", "--vault", tmp_vault.root)
    s = run_cli("status", "--json", "--vault", tmp_vault.root).json()
    assert s["raw"]["pending"] == 0 and s["index_stale"] is False


def test_status_text(run_cli, tmp_vault):
    r = run_cli("status", "--vault", tmp_vault.root)
    assert r.code == 0 and "pages:" in r.out and "pending" in r.out
