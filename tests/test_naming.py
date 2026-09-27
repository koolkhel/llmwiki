import unicodedata

import pytest

from conftest import (
    CASE_DUPES,
    CYRILLIC_TITLE,
    EMOJI_TITLE,
    ILLEGAL_TITLE,
    LINK_BREAKING_TITLE,
    LONG_CYRILLIC_TITLE,
    NFC_TITLE,
    NFD_TITLE,
    ONLY_ILLEGAL_TITLE,
    SYNTHETIC_TITLES,
)
from llmwiki.errors import WikiError
from llmwiki.naming import is_canonical_stem, key, title_to_filename


@pytest.mark.parametrize(
    "title, expected",
    [
        (ILLEGAL_TITLE, "A B Test.md"),
        (LINK_BREAKING_TITLE, "Heading Block ref x pipe.md"),
        ("  .hidden title. ", "hidden title.md"),
        ("tab\there\nnewline", "tab here newline.md"),
        (CYRILLIC_TITLE, f"{CYRILLIC_TITLE}.md"),
    ],
)
def test_sanitising(title, expected):
    assert title_to_filename(title) == expected


def test_nfd_becomes_nfc():
    name = title_to_filename(NFD_TITLE)
    assert name == f"{NFC_TITLE}.md"
    assert unicodedata.is_normalized("NFC", name)


def test_emoji_preserved():
    assert title_to_filename(EMOJI_TITLE) == f"{EMOJI_TITLE}.md"


def test_long_multibyte_truncation():
    name = title_to_filename(LONG_CYRILLIC_TITLE)
    assert name.endswith(".md")
    assert len(name.encode("utf-8")) <= 200
    assert set(name[:-3]) == {"Ж"}  # no partial character


def test_truncation_does_not_leave_trailing_space():
    title = "a" * 196 + " tail"
    stem = title_to_filename(title)[:-3]
    assert not stem.endswith(" ")


@pytest.mark.parametrize("title", [ONLY_ILLEGAL_TITLE, "", "   ", "..."])
def test_nothing_usable(title):
    with pytest.raises(WikiError) as e:
        title_to_filename(title)
    assert e.value.code == "empty_title"


@pytest.mark.parametrize("title", SYNTHETIC_TITLES)
def test_output_is_canonical(title):
    assert is_canonical_stem(title_to_filename(title)[:-3])


def test_key_case_and_normalisation():
    assert key(CASE_DUPES[0]) == key(CASE_DUPES[1])
    assert key(NFD_TITLE) == key(NFC_TITLE.upper())
    assert key("Page.md") == key("page")


def test_non_canonical_stems():
    assert not is_canonical_stem(NFD_TITLE)
    assert not is_canonical_stem("has: colon")
