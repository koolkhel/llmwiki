"""Supported wiki languages (code -> name). A fixed list, so every rendering of the
vault schema can be registered for `wiki upgrade`."""

LANGUAGES: dict[str, str] = {
    "en": "English",
    "ru": "Russian",
    "zh": "Chinese",
    "hi": "Hindi",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
}


def supported() -> str:
    return ", ".join(f"{c} ({n})" for c, n in LANGUAGES.items())


PER_SOURCE_RULE = "- Write in the language of the source unless the human asks otherwise."


def schema_values(code: str | None) -> dict[str, str]:
    """Placeholder values for the vault templates, for a wiki language (None = per-source)."""
    if code is None:
        return {"{{language_rule}}": PER_SOURCE_RULE, "{{language_section}}": "", "{{language_line}}": ""}
    name = LANGUAGES[code]
    section = f"""## Language

This vault's wiki language is **{name}**.

- Write every page title and all prose in {name}. Never translate, edit or
  re-save anything under `raw/`: sources stay in their original language.
- One concept or entity is one page, whatever language its sources use. List
  its names in other languages and scripts under `aliases:`, and add new ones
  as sources introduce them, e.g.
  `aliases: [Большая языковая модель, 大语言模型, बड़ा भाषा मॉडल, LLM]`.
- Quote the original text, followed by a translation into {name}.
- People: title the page with their established {name} name, and put the
  original-script name in `aliases` (e.g. `Fei-Fei Li` with `aliases: [李飞飞]`).
- Source pages copy `language` from the raw file's frontmatter.
- `wiki search` matches `aliases`, so search in any language before creating
  a page.

"""
    return {
        "{{language_rule}}": f"- Write every page in {name} (see **Language** below).",
        "{{language_section}}": section,
        "{{language_line}}": f'language = "{code}"\n',
    }
