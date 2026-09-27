import datetime as dt
import unicodedata

from conftest import EMOJI_TITLE, NFC_TITLE, NFD_TITLE
from llmwiki.pages import dump, iter_pages, new_page_meta, parse
from llmwiki.vault import Vault


def test_round_trip_keeps_key_order_and_unicode():
    meta = new_page_meta("concept", dt.date(2026, 9, 27))
    meta["summary"] = f"About {EMOJI_TITLE}"
    text = dump(meta, "Body line\n")
    doc = parse(text)
    assert doc.error is None
    assert list(doc.meta) == ["type", "summary", "sources", "tags", "created", "updated"]
    assert doc.meta["summary"] == f"About {EMOJI_TITLE}"
    assert doc.meta["created"] == dt.date(2026, 9, 27)
    assert doc.body.strip() == "Body line"
    assert "created: 2026-09-27\n" in text  # unquoted date


def test_parse_missing_and_invalid():
    assert parse("no frontmatter here").error == "missing"
    assert parse("---\n: : bad\n  - [\n---\nbody").error.startswith("unparseable")
    assert parse("---\n- a list\n---\n").error == "frontmatter is not a mapping"
    assert parse("---\n---\nbody").meta == {}


def test_parse_crlf():
    doc = parse("---\r\ntype: concept\r\n---\r\nbody\r\n")
    assert doc.meta == {"type": "concept"} and doc.body == "body\n"


def test_empty_body():
    doc = parse(dump({"type": "entity"}))
    assert doc.meta == {"type": "entity"} and doc.body == ""


def test_listing_normalises_nfd_and_skips_hidden(tmp_vault):
    tmp_vault.page("concept", NFD_TITLE)
    tmp_vault.page("entity", "Visible")
    hidden = tmp_vault.root / "wiki" / ".obsidian"
    hidden.mkdir()
    (hidden / "workspace.md").write_text("x")
    pages = iter_pages(Vault(tmp_vault.root))
    stems = {p.stem for p in pages}
    assert stems == {NFC_TITLE, "Visible"}
    nfd_page = next(p for p in pages if p.stem == NFC_TITLE)
    assert unicodedata.is_normalized("NFC", nfd_page.rel)
    assert nfd_page.fs_stem == NFD_TITLE  # on-disk form retained for lint
    assert nfd_page.folder_type == "concept"


def test_page_problems(tmp_vault):
    tmp_vault.page("concept", "Good")
    tmp_vault.page("source", "No Raw")
    tmp_vault.page("concept", "Bad Types", sources="not a list", type="bogus")
    by_stem = {p.stem: p for p in iter_pages(Vault(tmp_vault.root))}
    assert by_stem["Good"].problems() == []
    assert any("raw" in p for p in by_stem["No Raw"].problems())
    probs = by_stem["Bad Types"].problems()
    assert any("`type`" in p for p in probs) and any("`sources`" in p for p in probs)
