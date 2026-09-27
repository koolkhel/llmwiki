## Why

Some pages can't be captured by URL. gatesnotes.com, for example, answers every non-browser request with a 403 "Access Denied" from its CDN, whatever the User-Agent. The same happens with paywalls, logins and JavaScript-rendered pages. The user can save such a page from a browser, but `wiki add-source` accepts only `.txt` and `.md` files, so the saved `.html` can't be ingested. A spike showed that the existing URL extraction (trafilatura + mcmetadata) turns the saved page into a clean article, with title, date and language detected and no boilerplate. Only the input side is missing, so pandoc (a whole-page converter with no main-content detection) isn't needed.

## What Changes

- `wiki add-source <file.html|file.htm>` captures a browser-saved web page using the same extraction as URL capture. The original URL is detected from the page itself (`<link rel=canonical>`, then `og:url`, then Chrome's `<!-- saved from url=… -->` comment), or set with a new `--url <url>` option.
- A saved page with a known URL is recorded as `kind: url`, with `captured_via: saved-file` and `original_path`. It therefore deduplicates against direct URL captures of the same article, in either order.
- A saved page with no detectable URL and no `--url` is still captured, as `kind: file`, with a warning suggesting `--url`.
- The saved HTML is kept byte-for-byte in `raw/.orig/`. The browser's `…_files/` asset folder is ignored.
- Capturing a saved page makes no network requests.
- The vault templates (`AGENTS.md` and the ingest workflow) mention saved `.html` pages as a source and the "save from browser" route for pages that block fetching.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `source-capture`: adds a "Capture a saved web page" requirement. The existing file and URL requirements are unchanged. Duplicate detection already covers `kind: url` by normalized URL, and applies to saved pages through their recorded kind.

## Impact

- Code: `sources.py` (a new branch for `.html`/`.htm`), `fetch.py` (URL detection from markup; offline suffix data for file captures), `cli.py` (the `--url` option on `add-source`), the templates and tests.
- No new dependencies.
- `.mhtml` and Safari `.webarchive` stay unsupported (still `unsupported_file`).
