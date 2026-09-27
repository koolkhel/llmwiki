import unicodedata

import pytest

from llmwiki.morph import Analyzer, fold, tokenize

# --- fold --------------------------------------------------------------------


def test_fold_keeps_short_i():
    assert fold("мой") != fold("мои")
    assert fold("Йогурт") == "йогурт"


def test_fold_yo_to_ye():
    assert fold("Ёжик") == fold("ежик") == "ежик"


def test_fold_latin_diacritics_and_case():
    assert fold("Café") == "cafe"
    assert fold("STRAßE") == "strasse"


def test_fold_nfd_input():
    nfd = unicodedata.normalize("NFD", "йёé")
    assert fold(nfd) == "йеe"


def test_fold_drops_stress_marks():
    assert fold("сло́во") == "слово"


# --- tokenize ------------------------------------------------------------------


def _texts(text, **kw):
    return [t.text for t in tokenize(text, **kw)]


def test_tokenize_scripts_digits_punctuation():
    assert _texts("Кошки, cats & 42 котёнка! 🐱emoji") == ["Кошки", "cats", "42", "котёнка", "emoji"]


def test_tokenize_offsets_slice_back():
    text = "Привет, мир — hello world"
    for t in tokenize(text):
        assert text[t.start:t.end] == t.text


def test_tokenize_compounds():
    toks = tokenize("про нейро-сеть и e-mail")
    assert [t.text for t in toks] == ["про", "нейросеть", "нейро", "сеть", "и", "email", "e", "mail"]
    joined = next(t for t in toks if t.text == "нейросеть")
    assert "про нейро-сеть и e-mail"[joined.start:joined.end] == "нейро-сеть"
    assert _texts("нейро-сеть", compounds=False) == ["нейро", "сеть"]


def test_tokenize_underscore_splits_and_stress_mark_does_not():
    assert _texts("snake_case") == ["snake", "case"]
    assert _texts("сло́во") == ["сло́во"]


# --- keys ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def an():
    return Analyzer()


@pytest.mark.parametrize(
    "group",
    [
        ["кошка", "кошки", "кошкой", "кошек", "кошкам"],
        ["человек", "люди", "людей"],
        ["идти", "иду", "шёл", "шла"],
        ["хороший", "лучше"],
        ["организация", "организаций"],
        ["нейросеть", "нейросетями"],
        ["running", "runs", "run"],
    ],
)
def test_forms_share_a_key(an, group):
    common = frozenset.intersection(*(an.keys(w) for w in group))
    assert common, {w: an.keys(w) for w in group}


def test_ambiguous_word_gets_all_lemmas(an):
    assert {"бег", "бежать"} <= an.keys("бегу")


# Snowball merges these; lemmas keep them apart. (Not `вести`/`весть`: `вести` is also
# the plural of `весть`, and `мыло` a past form of `мыть`: sharing a key there is correct.)
@pytest.mark.parametrize("a, b", [("стать", "статья"), ("лес", "лесть")])
def test_no_false_merge(an, a, b):
    assert not (an.keys(a) & an.keys(b))


def test_yo_insensitive_lemmas(an):
    assert an.keys("ёжика") & an.keys("ежик")


def test_other_tokens_fold_only(an):
    assert an.keys("42") == {"42"}
    assert an.keys("iPhone15") == {"iphone15"}


def test_memo_and_new():
    a = Analyzer(memo={"кошек": frozenset({"кошка"})})
    assert a.keys("Кошек") == {"кошка"}
    assert a.new == {}
    a.keys("собак")
    assert list(a.new) == ["собак"]


def test_fast_fold_path_matches_char_by_char():
    import random

    from llmwiki.morph import _fold_char, fold_with_map

    rnd = random.Random(3)
    alphabet = "abcXYZ019 ,.-йЙёЁжЖщЩіїєґé ßİ—«»🚀́"
    for _ in range(300):
        s = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 40)))
        slow_out, slow_idx = [], []
        for i, ch in enumerate(s):
            p = _fold_char(ch)
            slow_out.append(p)
            slow_idx += [i] * len(p)
        assert fold_with_map(s) == ("".join(slow_out), slow_idx), s
