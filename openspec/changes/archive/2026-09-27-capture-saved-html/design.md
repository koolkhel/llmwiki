## Context

See proposal.md for motivation. Relevant current code:
- `fetch.extract(original_url, final_url, html, html_bytes) -> FetchedPage` already does all the extraction (mcmetadata metadata, trafilatura markdown body with a `text_content` fallback, `MIN_BODY_CHARS`, and `<title>`/canonical via `_html_bits`). `fetch.fetch()` only adds the HTTP step and the content-type check.
- `sources.capture()` sends http(s) arguments to `capture_url` and everything else to `capture_file`, which accepts only `.txt`/`.md` (`FILE_SUFFIXES`) and raises `unsupported_file` otherwise.
- `cli-conventions` already requires that no command other than `add-source <URL>` touches the network. mcmetadata calls `tldextract.extract()`, whose default instance downloads the public-suffix list on first use. The tests hide this because `conftest.py` swaps `tldextract.extract` for an offline instance in every test.

Spike (read-only, on the user's saved gatesnotes.com page: 154 kB plain `.html` plus a 64-file `_files/` folder):
- A direct fetch returns `403 Access Denied` (CDN), also with a Safari User-Agent. Saving from a browser is the only route.
- The page contains `<link rel="canonical">` and `<meta property="og:url">`, both pointing to the article, and no Chrome "saved from" comment.
- `fetch.extract(canonical, canonical, html, bytes)` gave: title correct, published `2026-08-26`, language `en`, extractor `trafilatura`, 5,914 words, 9 headings, no subscribe, cookie or navigation boilerplate. The cosmetics come from the page itself (a kicker line above the H1, one pull-quote repeated) and are left as they are.

## Goals / Non-Goals

**Goals:**
- One command for saved pages, with the same output quality and provenance as URL capture, deduplicated against URL captures.
- Strictly offline.

**Non-Goals:**
- `.mhtml`, `.webarchive` and PDF (stay `unsupported_file`).
- Capturing images or assets from `_files/`.
- Fetching the page through a headless browser to get around bot protection.
- pandoc: it converts the whole page, with no main-content detection or metadata, and is an external binary. It may come up again later for EPUB/DOCX.

## Decisions

### D1. Reuse `fetch.extract`, add `fetch.extract_saved(path_bytes, url_hint)`
A new function in `fetch.py`:
1. Decodes the bytes with the existing `_decode(content, None)` (the page's declared charset, or detection).
2. Detects the URL (D2).
3. Calls `extract(url, url, html, bytes)`.

When no URL is known, a placeholder `file:` URL is passed only so extraction runs; mcmetadata tolerates it (verified in a task). The URL-derived fields are then dropped from the result. The HTTP and content-type steps stay in `fetch()`.

### D2. URL detection order: `--url`, canonical, `og:url`, "saved from" comment
`_html_bits` is extended to also return `og:url` and the Chrome/IE `<!-- saved from url=(NNNN)URL -->` comment (the regex takes the URL after the length prefix). Relative canonical and `og:url` values are resolved against the other absolute signal when one exists. Only absolute `http(s)` URLs are accepted. The explicit `--url` always wins, because the user may know better; for example, some sites' canonical links point at a homepage.

### D3. Recorded as `kind: url` when a URL is known
This keeps saved pages first-class web sources: the same fields as URL capture, plus `captured_via: saved-file` and `original_path`, and `original_url` is the detected or given URL. The normalized-URL duplicate check therefore works in both directions, saved-after-direct and direct-after-saved. Without a URL, the page is recorded as `kind: file` with `extractor`, `original_file` and `original_path`, and the output carries a warning (via the existing `Outcome.warnings` path, which needs a small extension so that `capture` can return warnings).

### D4. `.orig` copy and naming
The saved bytes are copied unmodified to `raw/.orig/<raw stem>.html`, the same naming as URL captures. `_files/` is never read.

### D5. Offline suffix data, enforced in code
`fetch._extractors()` replaces the process-wide `tldextract.extract` with `tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)`, which uses the snapshot bundled with the package. This applies to URL capture too. That's acceptable because the bundled snapshot is fine for URL normalization, and it removes a hidden first-run download. The test for the "Offline" scenario undoes conftest's patch, installs a network-using default extractor with an empty cache directory, keeps the socket guard, and asserts that the capture succeeds. That proves the code's own safeguard, not the test harness's.

### D6. CLI
`add-source` gains `--url TEXT`. `sources.capture(vault, arg, url=None)` dispatches on suffix: `.html`/`.htm` go to `capture_saved_html`; `--url` with anything else raises `WikiError("invalid_option")`. The text output reads `captured raw/… (pending) — saved page, URL from canonical`. The JSON output adds `url_source: "option" | "canonical" | "og:url" | "saved-from" | null`.

### D7. Templates
- The ingest workflow's `argument-hint` becomes `<url | path to .txt/.md/.html> [focus or notes]`.
- Step 1 of the workflow gets a note: "If a URL fails with `http_error` 403/401 or `extraction_failed`, ask the human to save the page from a browser and give you the `.html` path."
- The `AGENTS.md` sources sentence mentions saved `.html` pages.

### D8. Verification and implementation notes (recorded during apply)
- **Real page, network blocked for the process** (socket connect, `create_connection` and `getaddrinfo` all patched to fail and record): `wiki add-source` on the saved gatesnotes.com page exited 0 with **0 network attempts**. It produced `kind: url`, `captured_via: saved-file`, `url_source: canonical`, the correct title, `published: 2026-08-26`, `language: en`, `extractor: trafilatura`, and **5,914 body words**, identical to the spike. The `.orig` copy's sha256 equals the saved file's, and the 64-file `_files/` folder was neither read nor copied. `wiki lint` then reported 0 errors and 0 warnings (1 info: pending source).
- A direct `wiki add-source https://www.gatesnotes.com/…` still fails with `http_error` 403 (exit 2), writing nothing. Re-adding the saved page reports `already captured`.
- **The offline test is real:** with `_offline_suffix_list` disabled, the test fails because tldextract tries to connect to `publicsuffix.org:443`. With it enabled there are no attempts. The test records attempts instead of relying on failures, because tldextract silently falls back to its snapshot when the download fails.
- mcmetadata accepts the `file:///saved-page.html` placeholder; `about:blank` raises `Invalid port`. The placeholder produces a bogus normalized URL (`http://file/saved-page.html`), which the no-URL path discards.
- `_source_file()` now holds the path checks shared by `.txt`/`.md` and `.html`/`.htm`. The `unsupported_file` message lists all four suffixes.

## Risks / Trade-offs

- [The canonical link points somewhere wrong, e.g. a homepage or an AMP page] → `--url` overrides it. `url_source` in the output shows where the URL came from, so Claude or the human can spot a bad one.
- [Replacing `tldextract.extract` globally could surprise other code in the process] → the CLI is a short-lived, single-purpose process, and the replacement only switches to the bundled data.
- [Browsers that save only the pre-JavaScript DOM give pages with little text] → the existing `MIN_BODY_CHARS` check fails with `extraction_failed` instead of storing junk. The ingest template says to save "as rendered", i.e. Webpage Complete.
- [The same article saved twice with small differences in the saved DOM] → the normalized-URL duplicate check catches it whenever the URL is known.

## Migration Plan

None. This is additive. Existing vaults get the updated ingest template only if its files are deleted and `wiki init` is re-run, as documented; the CLI works either way.

## Open Questions

None.
