from conftest import NFC_TITLE, NFD_TITLE
from llmwiki.links import Resolver, extract_links, links_in_meta, page_links
from llmwiki.pages import iter_pages
from llmwiki.vault import Vault


def _resolver(tmp_vault):
    v = Vault(tmp_vault.root)
    return Resolver(v, iter_pages(v))


def test_parse_forms():
    text = "See [[Plain]], [[Name|Alias]], [[Name#History|H]], [[Name#^blk1]], ![[image.png]] and [[folder/Page]]."
    links = extract_links(text)
    assert [(l.target, l.anchor, l.alias, l.embed) for l in links] == [
        ("Plain", None, None, False),
        ("Name", None, "Alias", False),
        ("Name", "History", "H", False),
        ("Name", "^blk1", None, False),
        ("image.png", None, None, True),
        ("folder/Page", None, None, False),
    ]


def test_code_is_ignored():
    text = "real [[One]] and `[[Not A Page]]` and ``x [[Nope]] y``\n```\n[[Fenced]]\n```\n~~~md\n[[Tilde]]\n~~~\nafter [[Two]]\n"
    assert [l.target for l in extract_links(text)] == ["One", "Two"]


def test_unclosed_fence_masks_rest():
    assert extract_links("[[A]]\n```\n[[B]]\n") and [l.target for l in extract_links("[[A]]\n```\n[[B]]\n")] == ["A"]


def test_links_in_frontmatter():
    meta = {"sources": ["[[Source One]]", "[[Source Two|S2]]"], "tags": ["x"], "raw": "raw/a.md"}
    assert [l.target for l in links_in_meta(meta)] == ["Source One", "Source Two"]


def test_resolve_alias_heading_case(tmp_vault):
    tmp_vault.page("concept", "Retrieval-Augmented Generation")
    r = _resolver(tmp_vault)
    (link,) = extract_links("[[retrieval-augmented generation#History|RAG]]")
    assert r.resolve(link.target) == "wiki/concepts/Retrieval-Augmented Generation.md"


def test_resolve_nfd_link_to_nfc_page(tmp_vault):
    tmp_vault.page("entity", NFC_TITLE)
    assert _resolver(tmp_vault).resolve(NFD_TITLE) == f"wiki/entities/{NFC_TITLE}.md"


def test_resolve_path_forms(tmp_vault):
    tmp_vault.page("concept", "Shared")
    r = _resolver(tmp_vault)
    assert r.resolve("wiki/concepts/Shared") == "wiki/concepts/Shared.md"
    assert r.resolve("concepts/shared") == "wiki/concepts/Shared.md"  # suffix match
    assert r.resolve("entities/Shared") is None


def test_resolve_raw_and_attachments(tmp_vault):
    raw = tmp_vault.raw("2026-01-01-Some Source", "text")
    (tmp_vault.root / "wiki" / "diagram.png").write_bytes(b"\x89PNG")
    r = _resolver(tmp_vault)
    assert r.resolve("2026-01-01-Some Source") == tmp_vault.rel(raw)
    assert r.resolve("diagram.png") == "wiki/diagram.png"
    assert r.resolve("Missing") is None
    assert r.resolve("") == ""


def test_hidden_dirs_not_resolved(tmp_vault):
    (tmp_vault.root / ".obsidian").mkdir()
    (tmp_vault.root / ".obsidian" / "Secret.md").write_text("x")
    assert _resolver(tmp_vault).resolve("Secret") is None


def test_page_links_combines_meta_and_body(tmp_vault):
    tmp_vault.page("concept", "C", body="Body [[B]]", sources=["[[S]]"])
    (page,) = iter_pages(Vault(tmp_vault.root))
    assert [l.target for l in page_links(page)] == ["S", "B"]
