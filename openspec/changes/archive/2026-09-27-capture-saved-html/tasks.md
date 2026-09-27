## 1. Extraction

- [x] 1.1 Extend `fetch._html_bits` to also return `og:url` and the "saved from" comment URL, resolving relative values and accepting only absolute http(s) URLs. Verify with unit tests on synthetic HTML for each signal, a relative canonical, a non-http value, and a page with none.
- [x] 1.2 Add `fetch.extract_saved(data, url_hint)` per D1/D2: decode, detect the URL in order (`--url`, canonical, og:url, saved-from), and extract. With no URL, check that mcmetadata accepts the placeholder URL and drop the URL fields. Return the page plus `url_source`. Verify with tests for the detection order, `--url` precedence, and the no-URL path (body extracted, no URL fields).
- [x] 1.3 Make `_extractors()` install the offline `tldextract` extractor per D5. Verify with a test that removes conftest's patch, installs a default (network-using) extractor with an empty cache directory, keeps the socket guard, and checks that a saved-page capture succeeds.

## 2. Capture and CLI

- [x] 2.1 Add `sources.capture_saved_html` per D3/D4: `kind: url` fields plus `captured_via`/`original_path` when a URL is known, `kind: file` and a warning otherwise, a byte-exact `.orig` copy, the duplicate check (sha256 and normalized URL), `_files/` untouched, and the saved file left as it was. Verify with tests for each spec scenario, including deduplication in both directions (saved after URL capture, and URL capture after saved) and `extraction_failed` writing nothing.
- [x] 2.2 Add `--url` to `add-source`, the `url_source` output field, the text-output wording, and warning pass-through from capture to `Outcome.warnings`. Reject `--url` for non-HTML sources and for URL arguments with `invalid_option` (exit 2). Verify with CLI tests: JSON fields, warnings in JSON and on stderr, and exit codes.

## 3. Templates and docs

- [x] 3.1 Update the ingest workflow template (`argument-hint` and the step-1 note for blocked pages) and the `AGENTS.md` source wording per D7, and the README command table. Verify that `test_init` passes and the new wording is present in both rendered workflow files.

## 4. Verification

- [x] 4.1 Run the real saved gatesnotes.com page through `wiki add-source` into a scratch vault (not the user's vaults), with the network blocked for the process. Check `kind: url`, `url_source: canonical`, the body's word count matching the spike (about 5.9k), and a byte-exact `.orig`. Then run `wiki add-source https://www.gatesnotes.com/a-turbulent-ai-era-and-critical-choices-to-make` and confirm the expected `http_error` 403 (no duplicate is written, since nothing is fetched). Record the results in design.md.
