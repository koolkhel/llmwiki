"""One test per lint code: a clean synthetic vault plus one defect yields exactly that finding."""

import hashlib

import pytest

from conftest import NFC_TITLE, NFD_TITLE
from llmwiki import index, lint
from llmwiki.vault import Vault


def _reindex(tmp_vault):
    index.write(Vault(tmp_vault.root))


@pytest.fixture
def clean(tmp_vault):
    """Two linked concept pages plus an ingested raw source; no findings."""
    raw = tmp_vault.raw("2026-01-01-Origin", "synthetic origin text")
    tmp_vault.page("source", "Origin", body="From raw. See [[Alpha]].", summary="the source", raw=tmp_vault.rel(raw))
    tmp_vault.page("concept", "Alpha", body="Links to [[Beta]].", summary="first", sources=["[[Origin]]"])
    tmp_vault.page("concept", "Beta", body="Back to [[Alpha]].", summary="second")
    _reindex(tmp_vault)
    return tmp_vault


def codes(tmp_vault):
    return sorted({f.code for f in lint.check(Vault(tmp_vault.root))})


def test_clean_fixture_has_no_findings(clean):
    assert lint.check(Vault(clean.root)) == []


def test_dead_link(clean):
    clean.page("concept", "Alpha", body="Links to [[Beta]] and [[Nonexistent]].", summary="first", sources=["[[Origin]]"])
    findings = lint.check(Vault(clean.root))
    assert [(f.code, f.path, f.target) for f in findings] == [
        ("dead_link", "wiki/concepts/Alpha.md", "[[Nonexistent]]")
    ]


def test_dead_link_in_frontmatter(clean):
    clean.page("concept", "Alpha", body="Links to [[Beta]].", summary="first", sources=["[[Origin]]", "[[Gone]]"])
    assert codes(clean) == ["dead_link"]


def test_duplicate_title(clean):
    clean.page("entity", "alpha", summary="dup")
    clean.page("concept", "Beta", body="Back to [[Alpha]] and [[entities/alpha]].", summary="second")
    _reindex(clean)
    findings = lint.check(Vault(clean.root))
    assert {f.code for f in findings} == {"duplicate_title"}
    assert {f.path for f in findings} == {"wiki/concepts/Alpha.md", "wiki/entities/alpha.md"}


def test_bad_filename_nfd(clean):
    clean.page("concept", NFD_TITLE, summary="nfd on disk")
    clean.page("concept", "Beta", body=f"Back to [[Alpha]] and [[{NFC_TITLE}]].", summary="second")
    _reindex(clean)
    assert codes(clean) == ["bad_filename"]


def test_bad_filename_illegal_chars(clean):
    (clean.root / "wiki" / "concepts" / "Has#Hash.md").write_text(
        (clean.root / "wiki" / "concepts" / "Beta.md").read_text()
    )
    clean.page("concept", "Beta", body="Back to [[Alpha]] and [[concepts/Has#Hash]].", summary="second")
    _reindex(clean)
    assert "bad_filename" in codes(clean)


def test_frontmatter_missing(clean):
    (clean.root / "wiki" / "concepts" / "Gamma.md").write_text("# Gamma\n\nNo frontmatter. [[Alpha]]\n")
    clean.page("concept", "Beta", body="Back to [[Alpha]] and [[Gamma]].", summary="second")
    _reindex(clean)
    assert codes(clean) == ["frontmatter_missing"]


def test_frontmatter_invalid(clean):
    clean.page("concept", "Beta", body="Back to [[Alpha]].", summary="second", tags="not-a-list")
    assert codes(clean) == ["frontmatter_invalid"]


def test_frontmatter_unparseable(clean):
    (clean.root / "wiki" / "concepts" / "Beta.md").write_text("---\nsummary: [unclosed\n---\nBack to [[Alpha]].\n")
    assert "frontmatter_invalid" in codes(clean)


def test_type_folder_mismatch(clean):
    clean.page("concept", "Beta", body="Back to [[Alpha]].", summary="second", type="entity")
    assert codes(clean) == ["type_folder_mismatch"]


def test_raw_missing(clean):
    clean.page("source", "Origin", body="See [[Alpha]].", summary="the source", raw="raw/nope.md")
    # the real raw file is now un-ingested too
    assert codes(clean) == ["pending_source", "raw_missing"]


def test_raw_modified(clean):
    raw = clean.root / "raw" / "2026-01-01-Origin.md"
    raw.write_text(raw.read_text().replace("synthetic origin text", "tampered text"))
    assert codes(clean) == ["raw_modified"]


def test_raw_without_capture_frontmatter(clean):
    (clean.root / "raw" / "dropped.md").write_text("clipped straight into raw/\n")
    assert codes(clean) == ["frontmatter_invalid", "pending_source"]


def test_orphan(clean):
    clean.page("analysis", "Lonely", summary="nobody links here")
    _reindex(clean)
    findings = lint.check(Vault(clean.root))
    assert [(f.code, f.severity, f.path) for f in findings] == [("orphan", "warning", "wiki/analyses/Lonely.md")]


def test_index_links_do_not_count_for_orphans(clean):
    clean.page("analysis", "Lonely", summary="x")
    _reindex(clean)
    assert "[[Lonely]]" in (clean.root / "index.md").read_text()
    assert codes(clean) == ["orphan"]


def test_empty_summary(clean):
    clean.page("concept", "Beta", body="Back to [[Alpha]].", summary="")
    _reindex(clean)
    assert codes(clean) == ["empty_summary"]


def test_index_stale(clean):
    clean.page("concept", "Beta", body="Back to [[Alpha]].", summary="changed summary")
    assert codes(clean) == ["index_stale"]


def test_pending_source(clean):
    clean.raw("2026-02-02-New", "new synthetic text")
    findings = lint.check(Vault(clean.root))
    assert [(f.code, f.severity) for f in findings] == [("pending_source", "info")]


# --- exit status, output, read-only ------------------------------------------


def test_exit_codes(run_cli, clean):
    assert run_cli("lint", "--vault", clean.root).code == 0
    clean.page("analysis", "Lonely", summary="x")
    _reindex(clean)
    assert run_cli("lint", "--vault", clean.root).code == 0  # warnings only
    assert run_cli("lint", "--strict", "--vault", clean.root).code == 1
    clean.page("concept", "Beta", body="[[Alpha]] [[Nowhere]]", summary="second")
    r = run_cli("lint", "--json", "--vault", clean.root)
    assert r.code == 1
    doc = r.json()
    assert doc["ok"] is False
    assert doc["counts"] == {"error": 1, "warning": 1, "info": 0}
    assert {f["code"] for f in doc["findings"]} == {"dead_link", "orphan"}


def test_info_does_not_fail_strict(run_cli, clean):
    clean.raw("2026-02-02-New", "new synthetic text")
    assert run_cli("lint", "--strict", "--vault", clean.root).code == 0


def _snapshot(root):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def test_lint_is_read_only(run_cli, clean):
    clean.page("concept", "Beta", body="[[Alpha]] [[Nowhere]]", summary="stale now")
    before = _snapshot(clean.root)
    run_cli("lint", "--vault", clean.root)
    run_cli("lint", "--json", "--strict", "--vault", clean.root)
    assert _snapshot(clean.root) == before


def test_text_output(run_cli, clean):
    clean.page("concept", "Beta", body="[[Alpha]] [[Nowhere]]", summary="second")
    r = run_cli("lint", "--vault", clean.root)
    assert "dead_link" in r.out and "1 error(s)" in r.out
