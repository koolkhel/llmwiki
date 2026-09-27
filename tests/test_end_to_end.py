"""Full workflow on a temp vault, as Claude Code would drive it (stubbed web)."""

import pytest

from conftest import EMOJI_TITLE
from fakeweb import FakeWeb, article_html
from llmwiki import fetch


@pytest.fixture
def web(monkeypatch):
    fw = FakeWeb()
    monkeypatch.setattr(fetch, "http_get", fw)
    return fw


def test_ingest_workflow(run_cli, web, tmp_path):
    v = tmp_path / "vault"
    web.add("https://example.org/widgets", article_html("Synthetic Widgets"))
    notes = tmp_path / "meeting.txt"
    notes.write_text(f"Synthetic meeting notes about {EMOJI_TITLE} and widgets.\n")

    def wiki(*args):
        r = run_cli(*args, "--json", "--vault", v)
        return r.code, r.json()

    assert run_cli("init", v, "--json", "--no-git").code == 0

    code, url_src = wiki("add-source", "https://example.org/widgets")
    assert code == 0 and url_src["status"] == "pending"
    code, file_src = wiki("add-source", str(notes))
    assert code == 0

    code, st = wiki("status")
    assert st["raw"]["pending"] == 2

    code, src_page = wiki("new-page", "--type", "source", "Synthetic Widgets", "--raw", url_src["path"])
    assert code == 0
    code, concept = wiki("new-page", "--type", "concept", "Widget")
    code, entity = wiki("new-page", "--type", "entity", EMOJI_TITLE)
    assert entity["link"] == f"[[{EMOJI_TITLE}]]"

    # What Claude would write: summaries, sources and cross-links.
    def write(page, summary, body, sources=()):
        path = v / page["path"]
        text = path.read_text()
        text = text.replace('summary: \'\'', f"summary: {summary}")
        if sources:
            text = text.replace("sources: []", "sources:\n" + "".join(f'- "{s}"\n' for s in sources))
        path.write_text(text + body)

    write(src_page, "Article introducing widgets", f"Touches {concept['link']} and {entity['link']}.\n")
    write(concept, "A small synthetic device", f"Built by {entity['link']}.\n", [src_page["link"]])
    write(entity, "Synthetic maker of widgets", f"Makes {concept['link']}.\n", [src_page["link"]])

    code, lint_before = wiki("lint")
    assert {f["code"] for f in lint_before["findings"]} == {"index_stale", "pending_source"}

    code, idx = wiki("index")
    assert idx["changed"] and idx["pages"] == 3
    code, entry = wiki("log", "ingest", "Synthetic Widgets")
    assert code == 0

    code, found = wiki("search", "widget", "--type", "concept")
    assert [r["title"] for r in found["results"]] == ["Widget"]

    code, st = wiki("status")
    assert st["raw"] == {"total": 2, "ingested": 1, "pending": 1}
    assert st["pending"][0]["path"] == file_src["path"]
    assert st["index_stale"] is False
    assert st["last_log"] == entry["entry"]

    code, final = wiki("lint", "--strict")
    assert code == 0, final
    assert [f["code"] for f in final["findings"]] == ["pending_source"]
