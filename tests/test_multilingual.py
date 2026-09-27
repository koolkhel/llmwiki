"""Multilingual vaults (multilingual-vault change). All text is synthetic."""

from __future__ import annotations

import pytest

from llmwiki.errors import WikiError
from llmwiki.languages import LANGUAGES
from llmwiki.vault import Vault, language


# --- 1.1 language setting -------------------------------------------------------------


def _vault_with_toml(tmp_path, text):
    (tmp_path / "llmwiki.toml").write_text(text, encoding="utf-8")
    return Vault(tmp_path)


def test_language_unset(tmp_path):
    assert language(_vault_with_toml(tmp_path, "layout_version = 1\n")) is None


@pytest.mark.parametrize("code", sorted(LANGUAGES))
def test_language_supported(tmp_path, code):
    assert language(_vault_with_toml(tmp_path, f'layout_version = 1\nlanguage = "{code}"\n')) == code


@pytest.mark.parametrize("text", ['language = "xx"\n', "language = 5\n", "layout_version = = 1\n"])
def test_language_invalid(tmp_path, text):
    with pytest.raises(WikiError) as e:
        language(_vault_with_toml(tmp_path, text))
    assert e.value.code == "invalid_language"


# --- 1.2 init --language --------------------------------------------------------------


def test_init_english(run_cli, tmp_path):
    v = tmp_path / "ai"
    r = run_cli("init", v, "--language", "en", "--json", "--no-git")
    assert r.code == 0 and r.json()["language"] == "en"
    assert 'language = "en"' in (v / "llmwiki.toml").read_text()
    assert language(Vault(v)) == "en"
    agents = (v / "AGENTS.md").read_text()
    assert "## Language" in agents and "wiki language is **English**" in agents
    for rule in ("Never translate", "aliases:", "followed by a translation into English",
                 "original-script name in `aliases`", "copy `language` from the raw file"):
        assert rule in agents, rule
    assert "language of the source" not in agents
    assert "language: English (en)" in run_cli("init", tmp_path / "ai2", "--language", "en", "--no-git").out
    assert run_cli("lint", "--strict", "--vault", v).code == 0


def test_init_unsupported_language(run_cli, tmp_path):
    v = tmp_path / "x"
    r = run_cli("init", v, "--language", "xx", "--json", "--no-git")
    assert r.code == 2 and r.json()["error"]["code"] == "invalid_language"
    assert "en (English)" in r.json()["error"]["message"]
    assert not v.exists()


def test_init_without_language(run_cli, tmp_path):
    v = tmp_path / "plain"
    run_cli("init", v, "--no-git")
    assert "language" not in (v / "llmwiki.toml").read_text()
    agents = (v / "AGENTS.md").read_text()
    assert "Write in the language of the source" in agents and "## Language" not in agents


# --- 2.1 upgrade follows the language ---------------------------------------------------

from llmwiki import upgrade  # noqa: E402


def test_switch_to_english_via_upgrade(run_cli, tmp_path):
    v = tmp_path / "v"
    run_cli("init", v, "--no-git")
    toml = v / "llmwiki.toml"
    toml.write_text(toml.read_text() + 'language = "en"\n')
    toml_before = toml.read_bytes()
    report, _ = upgrade.run(Vault(v))
    assert {i["path"]: i["action"] for i in report["items"]}["AGENTS.md"] == "update"
    assert "## Language" in (v / "AGENTS.md").read_text()
    assert toml.read_bytes() == toml_before
    again, _ = upgrade.run(Vault(v))
    assert {i["action"] for i in again["items"]} == {"unchanged"}


def test_untouched_other_language_is_unchanged(run_cli, tmp_path):
    v = tmp_path / "ru"
    run_cli("init", v, "--language", "ru", "--no-git")
    report, _ = upgrade.run(Vault(v))
    assert {i["action"] for i in report["items"]} == {"unchanged"}
    assert run_cli("status", "--json", "--vault", v).json()["templates"]["outdated"] == []


def test_invalid_language_in_toml_is_an_error(run_cli, tmp_path):
    v = tmp_path / "bad"
    run_cli("init", v, "--no-git")
    (v / "llmwiki.toml").write_text((v / "llmwiki.toml").read_text() + 'language = "klingon"\n')
    r = run_cli("upgrade", "--json", "--vault", v)
    assert r.code == 2 and r.json()["error"]["code"] == "invalid_language"


# --- 3.1 Indic scripts ------------------------------------------------------------------

import unicodedata  # noqa: E402

from llmwiki.morph import fold, query_words, tokenize  # noqa: E402

HINDI = "बड़े भाषा मॉडल को हिंदी में प्रशिक्षित किया गया"


def test_hindi_words_stay_whole():
    assert [t.text for t in tokenize(HINDI)] == ["बड़े", "भाषा", "मॉडल", "को", "हिंदी", "में", "प्रशिक्षित", "किया", "गया"]


def test_hindi_fold_keeps_virama_and_nukta():
    assert fold("प्रशिक्षित") != fold("परशिकषित")
    assert fold("बड़े") != fold("बडे")
    precomposed, decomposed = "ड़", "ड़"  # ड़ as one code point vs ड + nukta
    assert fold(precomposed) == fold(decomposed)


def test_latin_and_cyrillic_folding_unchanged():
    assert fold("Café") == "cafe"
    assert fold("сло́во") == "слово"  # Russian stress mark still dropped
    assert fold("Ёжик") == "ежик" and fold("мой") != fold("мои")


def test_hindi_search_exact(run_cli, tmp_vault):
    tmp_vault.page("concept", "Trained", body="मॉडल को प्रशिक्षित किया गया")
    tmp_vault.page("concept", "Broken", body="मॉडल को परशिकषित किया गया")
    r = run_cli("search", "प्रशिक्षित", "--json", "--vault", tmp_vault.root).json()
    assert [(x["title"], x["match"]) for x in r["results"]] == [("Trained", "exact")]


def test_mark_class_build_is_cheap():
    import time

    from llmwiki import morph

    morph._mark_patterns.cache_clear()
    t = time.perf_counter()
    morph._mark_patterns()
    assert time.perf_counter() - t < 0.2  # measured ~9 ms; generous bound for slow CI


# --- 3.2 CJK two-character pieces ---------------------------------------------------------

ZH = "大语言模型的训练需要大量数据"


def test_cjk_bigram_tokens():
    toks = tokenize(ZH)
    texts = [t.text for t in toks]
    assert ZH in texts and "模型" in texts and "训练" in texts
    t = next(t for t in toks if t.text == "训练")
    assert ZH[t.start:t.end] == "训练"


def test_cjk_query_words():
    assert query_words("大语言模型") == ["大语", "语言", "言模", "模型"]
    assert query_words("模") == ["模"]
    assert query_words("GPT 模型") == ["GPT", "模型"]


def test_cjk_search_exact_and_snippet(run_cli, tmp_vault):
    tmp_vault.page("concept", "Chinese Note", body="开头的文字。" + ZH)
    for q in ("模型", "训练", "大语言模型"):
        res = run_cli("search", q, "--json", "--vault", tmp_vault.root).json()["results"]
        assert [(x["title"], x["match"]) for x in res] == [("Chinese Note", "exact")], q
    assert "训练" in run_cli("search", "训练", "--json", "--vault", tmp_vault.root).json()["results"][0]["snippet"]


def test_cjk_single_character_substring(run_cli, tmp_vault):
    tmp_vault.page("concept", "Chinese Note", body=ZH)
    res = run_cli("search", "模", "--json", "--vault", tmp_vault.root).json()["results"]
    assert [x["match"] for x in res] == ["substring"]


# --- 4.1 aliases -------------------------------------------------------------------------


@pytest.fixture
def four_lang(tmp_vault):
    tmp_vault.page("concept", "Large language model", summary="neural LMs trained on huge corpora",
                   aliases=["Большая языковая модель", "大语言模型", "बड़ा भाषा मॉडल", "LLM"], body="An English body.")
    tmp_vault.page("concept", "Reinforcement learning", summary="learning from rewards", body="Mentions a model once.")
    tmp_vault.page("entity", "Fei-Fei Li", summary="AI researcher", aliases=["李飞飞"], tags=["person"])
    tmp_vault.page("source", "Vision talk", summary="talk", raw="raw/v.md", authors=["[[Fei-Fei Li]]"])
    return tmp_vault


@pytest.mark.parametrize("query", ["языковая модель", "языковой модели", "大语言模型", "模型", "भाषा मॉडल", "llm"])
def test_query_in_any_language_finds_concept(run_cli, four_lang, query):
    res = run_cli("search", query, "--json", "--vault", four_lang.root).json()["results"]
    assert res and res[0]["title"] == "Large language model", query
    assert res[0]["score"] >= 100  # ranked as a title match


def test_author_via_person_page_alias(run_cli, four_lang):
    res = run_cli("search", "--author", "李飞飞", "--json", "--vault", four_lang.root).json()["results"]
    assert [x["title"] for x in res] == ["Vision talk"]


def test_string_aliases(run_cli, tmp_vault):
    tmp_vault.page("concept", "Transformer", aliases="Трансформер", body="x")
    res = run_cli("search", "трансформер", "--json", "--vault", tmp_vault.root).json()["results"]
    assert [x["title"] for x in res] == ["Transformer"]
