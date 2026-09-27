"""Delta-spec scenarios for word-form-aware search (search-morphology change)."""

import os
import shutil

import pytest


def _search(run_cli, tmp_vault, *args):
    r = run_cli("search", *args, "--json", "--vault", tmp_vault.root)
    assert r.code == 0, r.out + r.err
    return r.json()


def _titles(res):
    return [r["title"] for r in res["results"]]


def _by_title(res):
    return {r["title"]: r for r in res["results"]}


def test_russian_case_forms(run_cli, tmp_vault):
    tmp_vault.page("concept", "Питомцы", body="Про кошек и о том, как жить с кошкой.")
    res = _search(run_cli, tmp_vault, "кошка")
    assert _titles(res) == ["Питомцы"]
    assert res["results"][0]["match"] == "lemma"
    assert "кошек" in res["results"][0]["snippet"]


def test_irregular_russian_forms(run_cli, tmp_vault):
    tmp_vault.page("concept", "Прогулка", body="Он шёл по улице.")
    tmp_vault.page("concept", "Толпа", body="На площади были люди.")
    assert _titles(_search(run_cli, tmp_vault, "идти")) == ["Прогулка"]
    assert _titles(_search(run_cli, tmp_vault, "человек")) == ["Толпа"]


def test_english_stems(run_cli, tmp_vault):
    tmp_vault.page("concept", "Daily", body="She runs every morning.")
    res = _search(run_cli, tmp_vault, "running")
    assert _titles(res) == ["Daily"] and res["results"][0]["match"] == "lemma"


def test_exact_outranks_lemma_same_field(run_cli, tmp_vault):
    tmp_vault.page("concept", "B", body="Много кошек.")
    tmp_vault.page("concept", "A", body="Одна кошка.")
    res = _search(run_cli, tmp_vault, "кошка")
    assert _titles(res) == ["A", "B"]
    assert [r["match"] for r in res["results"]] == ["exact", "lemma"]


def test_field_outranks_tier(run_cli, tmp_vault):
    # A lemma match in the summary beats an exact match in the body.
    tmp_vault.page("concept", "Summary Lemma", summary="о кошках")
    tmp_vault.page("concept", "Body Exact", body="кошка")
    res = _search(run_cli, tmp_vault, "кошка")
    t = _titles(res)
    assert t.index("Summary Lemma") < t.index("Body Exact")


def test_substring_kept(run_cli, tmp_vault):
    tmp_vault.page("concept", "Сети", body="Обучение: нейросеть и данные.")
    res = _search(run_cli, tmp_vault, "нейро")
    assert _titles(res) == ["Сети"] and res["results"][0]["match"] == "substring"


def test_short_i_is_not_i(run_cli, tmp_vault):
    tmp_vault.page("concept", "Сам", body="мои вещи")
    res = _search(run_cli, tmp_vault, "мой")
    # Not via exact or substring (й ≠ и); only via the shared lemma `мой`.
    assert [r["match"] for r in res["results"]] == ["lemma"]
    assert _search(run_cli, tmp_vault, "мой", "--exact")["results"] == []


def test_yo_matches_ye(run_cli, tmp_vault):
    tmp_vault.page("concept", "Ёжик в тумане")
    res = _search(run_cli, tmp_vault, "ежик")
    assert _titles(res) == ["Ёжик в тумане"] and res["results"][0]["match"] == "exact"


def test_exact_mode(run_cli, tmp_vault):
    tmp_vault.page("concept", "One", body="кошка")
    tmp_vault.page("concept", "Two", body="кошек")
    tmp_vault.page("concept", "Three", body="кошкарня")
    res = _search(run_cli, tmp_vault, "кошка", "--exact")
    assert _titles(res) == ["One"] and res["exact"] is True


def test_raw_uses_same_matching(run_cli, tmp_vault):
    tmp_vault.raw("2026-01-01-Clip", "Сюда пришло много людей.")
    res = _search(run_cli, tmp_vault, "человек", "--raw")
    assert [r["path"] for r in res["results"]] == ["raw/2026-01-01-Clip.md"]
    assert res["results"][0]["match"] == "lemma"


def test_all_terms_across_tiers(run_cli, tmp_vault):
    tmp_vault.page("concept", "Mixed", body="Кошек кормили утром; нейросеть считала.")
    tmp_vault.page("concept", "Half", body="Кошек кормили.")
    res = _search(run_cli, tmp_vault, "кошка", "нейро")
    assert _titles(res) == ["Mixed"] and res["results"][0]["match"] == "substring"


def test_hyphenated_compound(run_cli, tmp_vault):
    tmp_vault.page("concept", "Hyph", body="про нейро-сеть")
    assert _titles(_search(run_cli, tmp_vault, "нейросеть")) == ["Hyph"]
    assert _titles(_search(run_cli, tmp_vault, "сеть")) == ["Hyph"]


def test_deleting_cache_gives_identical_results(run_cli, tmp_vault):
    tmp_vault.page("concept", "A", body="кошка людей шёл")
    tmp_vault.page("concept", "B", summary="кошки", body="running")
    first = _search(run_cli, tmp_vault, "кошка")
    cache = tmp_vault.root / ".llmwiki" / "cache"
    assert (cache / "lemmas.sqlite").is_file()
    warm = _search(run_cli, tmp_vault, "кошка")
    shutil.rmtree(cache)
    cold = _search(run_cli, tmp_vault, "кошка")
    assert first == warm == cold


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_unwritable_cache_warns_but_works(run_cli, tmp_vault):
    tmp_vault.page("concept", "A", body="кошек")
    (tmp_vault.root / ".llmwiki").mkdir()
    os.chmod(tmp_vault.root / ".llmwiki", 0o500)
    try:
        r = run_cli("search", "кошка", "--json", "--vault", tmp_vault.root)
        assert r.code == 0
        doc = r.json()
        assert _titles(doc) == ["A"]
        assert any("search cache unavailable" in w for w in doc["warnings"])
    finally:
        os.chmod(tmp_vault.root / ".llmwiki", 0o700)


def test_cache_is_not_a_page(run_cli, tmp_vault):
    tmp_vault.page("concept", "A", body="кошка")
    _search(run_cli, tmp_vault, "кошка")
    assert run_cli("lint", "--vault", tmp_vault.root).code == 0
    s = run_cli("status", "--json", "--vault", tmp_vault.root).json()
    assert s["pages"]["concept"] == 1


def test_text_output_shows_match(run_cli, tmp_vault):
    tmp_vault.page("concept", "A", body="кошек")
    r = run_cli("search", "кошка", "--vault", tmp_vault.root)
    assert "lemma" in r.out
