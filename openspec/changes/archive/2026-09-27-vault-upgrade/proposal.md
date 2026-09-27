## Why

`wiki init` never overwrites files, so improvements to the vault templates never reach existing vaults. After `track-authors`, the user's vault agent correctly reported "AGENTS.md has no authors rule yet". Updating by hand (delete the workflow files, re-init, diff `AGENTS.md` against a fresh vault) is tedious and error-prone, and it will recur with every template change. The CLI can tell reliably whether a vault file is untouched: every file content `wiki init` has ever written is known (5 template-changing commits, at most 3 versions per file). So untouched files can be upgraded safely, and edited ones handed to the agent to merge.

## What Changes

- New **`wiki upgrade [--dry-run] [--json]`**. It compares each template-managed vault file with a shipped registry of every template version ever released:
  - missing: create;
  - current: nothing to do;
  - an older version: replace;
  - edited: write `<file>.new` next to it and report a conflict;
  - obsolete path, still the untouched old content: delete;
  - obsolete path, edited: keep it and warn.

  It never touches `raw/`, `wiki/`, `index.md`, `log.md` or `llmwiki.toml`, and warns about uncommitted changes.
- **The Claude Code commands are renamed** to `/wiki-ingest`, `/wiki-query` and `/wiki-lint`, matching Kimi Code's `/skill:wiki-*` and avoiding clashes with built-in commands. `wiki upgrade` migrates existing vaults: the old untouched `ingest.md`/`query.md`/`lint.md` are deleted as obsolete.
- **A new `upgrade` workflow** (`/wiki-upgrade` in Claude Code, `/skill:wiki-upgrade` in Kimi Code). It shows the dry run, runs the upgrade, merges each `.new` into the user's edited file (keeping their customisations), shows the diff for approval, deletes the `.new`, lints, commits, and tells the user to restart the agent session.
- **`wiki status`** reports template freshness (outdated, edited, obsolete and missing files, plus pending `.new` merges) and suggests `wiki upgrade`.
- **`wiki lint`** reports a leftover `<file>.new` as `template_merge_pending` (info).
- The README documents the command names, `wiki upgrade`, `/wiki-upgrade`, and "after updating the tool, run `wiki upgrade` in each vault".

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `vault-init`: "Agent integration files" changes to the `wiki-` command names and adds the upgrade workflow. A new requirement, "Upgrade vault templates", is added.
- `wiki-navigation`: "Vault status" gains the template freshness report.
- `wiki-lint`: "Structural checks" gains `template_merge_pending`.

## Impact

- Code: a new `upgrade.py` (planning and applying), `scaffold.py` (Claude command file names, the new workflow), `status.py`, `lint.py` and `cli.py`; a new `templates/workflows/upgrade.md`; a new packaged `templates/known_hashes.json` plus a dev script, `scripts/known_hashes.py`, that maintains it; the README; tests.
- **Breaking for habits:** in Claude Code, `/ingest`, `/query` and `/lint` become `/wiki-ingest`, `/wiki-query` and `/wiki-lint` once a vault is upgraded or created.
- No new dependencies.
