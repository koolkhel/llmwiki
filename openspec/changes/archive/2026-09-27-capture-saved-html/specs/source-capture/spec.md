## ADDED Requirements

### Requirement: Capture a saved web page
`wiki add-source <path>` for a `.html` or `.htm` file SHALL extract the page's main text as markdown with the same extraction used for URL capture, and write it to a new file under `raw/`. The original URL SHALL be taken from `--url <url>` if given, else from the page's `<link rel="canonical">`, else from its `og:url` meta tag, else from a `<!-- saved from url=… -->` comment. Relative values are resolved against the others where possible, and only `http(s)` URLs are accepted.

When a URL is known, the frontmatter SHALL be that of a URL capture (`kind: url`, `original_url`, `canonical_url` when known, `normalized_url`, `title`, `captured_at`, `sha256`, `extractor`, `original_file`, and `published`/`language` when available), plus `captured_via: saved-file` and `original_path` (absolute). When no URL is known, the frontmatter SHALL use `kind: file` with `title`, `original_path`, `captured_at`, `sha256`, `extractor` and `original_file`, and the command SHALL succeed with a warning that suggests `--url`.

The saved file's bytes SHALL be copied unmodified to `raw/.orig/` and referenced as `original_file`. Companion asset folders (such as `<name>_files/`) SHALL be ignored. The saved file SHALL NOT be modified or moved. Capturing a saved page SHALL NOT access the network. Duplicate detection SHALL apply as for other sources, so a saved page and a direct capture of the same URL are duplicates of each other. `--url` SHALL be rejected as a usage error for sources that are not `.html`/`.htm` files.

#### Scenario: Saved page with canonical URL
- **WHEN** the user runs `wiki add-source "~/Downloads/Article.html"` and the page has `<link rel="canonical" href="https://example.org/post">`
- **THEN** a raw file is created with `kind: url`, `captured_via: saved-file`, `original_url: https://example.org/post`, the extracted article as markdown, and an unmodified copy of the HTML under `raw/.orig/`

#### Scenario: URL from og:url or the saved-from comment
- **WHEN** a saved page has no canonical link but has an `og:url` meta tag, or only a `<!-- saved from url=(0027)https://example.org/post -->` comment
- **THEN** that URL is recorded as `original_url`

#### Scenario: Explicit URL wins
- **WHEN** the user passes `--url https://example.org/real` for a page whose canonical link says something else
- **THEN** `original_url` is `https://example.org/real`

#### Scenario: No URL known
- **WHEN** a saved page contains none of the URL signals and no `--url` is given
- **THEN** the page is captured with `kind: file`, the command exits 0, and the output includes a warning suggesting `--url`

#### Scenario: Duplicate of a direct URL capture
- **WHEN** `https://example.org/post` was captured by URL earlier, and a saved copy of the same article (canonical `https://example.org/post?utm_source=x`) is added
- **THEN** no new raw file is written and the output reports `duplicate_of` with the earlier file

#### Scenario: Offline
- **WHEN** a saved page is captured while network access is unavailable
- **THEN** the capture succeeds and no network connection is attempted

#### Scenario: Nothing extractable
- **WHEN** the saved page has no extractable main text
- **THEN** the command exits with code 2 (`extraction_failed`) and writes nothing to `raw/`

#### Scenario: --url on a non-HTML source
- **WHEN** the user runs `wiki add-source notes.txt --url https://example.org`
- **THEN** the command exits with code 2 and writes nothing
