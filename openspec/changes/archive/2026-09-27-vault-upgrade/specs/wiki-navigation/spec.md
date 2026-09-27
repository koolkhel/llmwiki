## MODIFIED Requirements

### Requirement: Vault status
`wiki status` SHALL report the vault path, page counts per type, total and pending raw source counts, the list of pending raw sources, whether `index.md` is stale, and the most recent log entry heading. It SHALL also report template freshness: the counts of template-managed files that are outdated (a known older version), edited, missing, and obsolete, plus the paths with a pending `<path>.new` merge. The human-readable output SHALL suggest `wiki upgrade` when anything is outdated, missing or obsolete. Computing template freshness SHALL NOT write any file.

#### Scenario: Status after capture
- **WHEN** one URL has been captured but no source page references it
- **THEN** `wiki status --json` reports one pending source with its path and title

#### Scenario: Outdated templates reported
- **WHEN** a vault still has an untouched older `AGENTS.md` and the old `.claude/commands/ingest.md`
- **THEN** `wiki status --json` reports `AGENTS.md` as outdated and `ingest.md` as obsolete, and the text output suggests `wiki upgrade`

#### Scenario: Fresh vault
- **WHEN** `wiki status` runs on a vault just created by the current `wiki init`
- **THEN** it reports no outdated, edited, missing or obsolete templates and no pending merges
