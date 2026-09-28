## ADDED Requirements

### Requirement: Commentary filter and outlet in results
`wiki search --commentary` SHALL restrict results to pages whose frontmatter has `commentary: true`. With `--raw` it SHALL be a usage error. It SHALL combine with query terms and with every other filter. When it is given, query terms SHALL be optional, as with `--author`. Search results and timeline entries SHALL include `outlet` when the source page has one.

#### Scenario: Only commented items
- **WHEN** two item pages mention «градирня», and only one has `commentary: true`
- **THEN** `wiki search градирня --commentary` returns only that one

#### Scenario: Commented items in a period
- **WHEN** the user runs `wiki search --commentary --since 2026-09 --sort newest`
- **THEN** all commented item pages published in September 2026 or later are returned, newest first

#### Scenario: Outlet shown
- **WHEN** an item page has `outlet: Вестник` and appears in a search result or a timeline
- **THEN** that result or entry includes `outlet: "Вестник"`

#### Scenario: Not for raw search
- **WHEN** the user runs `wiki search градирня --raw --commentary`
- **THEN** the command exits 2 with a usage error
