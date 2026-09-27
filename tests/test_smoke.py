import unicodedata

from conftest import NFC_TITLE, NFD_TITLE, SYNTHETIC_TITLES


def test_package_imports():
    import llmwiki

    assert llmwiki.__version__


def test_corpus_properties():
    assert NFD_TITLE != NFC_TITLE
    assert unicodedata.is_normalized("NFC", NFC_TITLE)
    assert any(len(t.encode()) > 200 for t in SYNTHETIC_TITLES)


def test_tmp_vault_layout(tmp_vault):
    assert (tmp_vault.root / "llmwiki.toml").is_file()
    assert (tmp_vault.root / "wiki" / "concepts").is_dir()
