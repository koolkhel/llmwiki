## ADDED Requirements

### Requirement: Mark digest captures
When `wiki add-source` captures a page from rossaprimavera.ru, whether by URL or from a saved `.html` whose original URL is on that site, and the captured HTML contains digest dateline paragraphs, the raw file's frontmatter SHALL include `format: rp-digest`. No other capture SHALL receive a `format` field. The body extraction SHALL be unchanged, and existing raw files SHALL NOT be rewritten.

#### Scenario: Digest URL
- **WHEN** the user captures a rossaprimavera.ru digest page with datelines
- **THEN** the raw file's frontmatter has `format: rp-digest`

#### Scenario: Ordinary article on the same site
- **WHEN** the user captures a rossaprimavera.ru article without datelines
- **THEN** the raw file has no `format` field

#### Scenario: Other site with the same markup
- **WHEN** a page on another domain happens to use `class="block_date"` paragraphs
- **THEN** the raw file has no `format` field
