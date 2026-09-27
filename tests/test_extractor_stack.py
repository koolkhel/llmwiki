"""Smoke test: the pinned extractor stack imports and works offline on this Python."""

import warnings

SYNTHETIC_HTML = """<html><head><title>Synthetic Widget Article</title></head><body>
<nav>menu</nav><article><h1>Synthetic Widget Article</h1><h2>Background</h2>
""" + "".join(
    f"<p>Synthetic paragraph {i} about widgets and gizmos, long enough to look like an "
    f"article body for the extractor. See <a href='https://example.org/{i}'>ref</a>.</p>"
    for i in range(6)
) + "<ul><li>first item</li><li>second item</li></ul></article><footer>f</footer></body></html>"


def test_mcmetadata_and_trafilatura_offline():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import mcmetadata
        import trafilatura

    meta = mcmetadata.extract(url="https://example.org/post?utm_source=x", html_text=SYNTHETIC_HTML)
    assert meta["article_title"] == "Synthetic Widget Article"
    assert "utm_source" not in meta["normalized_url"]

    body = trafilatura.extract(SYNTHETIC_HTML, include_formatting=True, include_links=True)
    assert "## Background" in body
    assert "- first item" in body
    assert "[ref](https://example.org/0)" in body
