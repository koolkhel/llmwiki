## Context

See proposal.md for motivation. Current state:
- `scaffold.planned_files(values)` returns every vault-relative path `init` renders, mapped to its content: `templates/vault/` copied (with `dot-` becoming `.`), plus `render_workflow()` output for each `templates/workflows/*.md`, as `.claude/commands/<name>.md` and `.agents/skills/wiki-<name>/SKILL.md`. `init_vault` writes only missing files.
- Only `llmwiki.toml` has placeholders (`{{layout_version}}`, `{{date}}`). `log.md` is seeded once and then appended to, so it is content. `index.md` is generated from pages.
- Claude command names are unprefixed (`/ingest`, `/query`, `/lint`), while Kimi skills are `wiki-*`. `AGENTS.md`, the workflow bodies, `scaffold.render_text` and the README reference the Claude names, and `test_no_bare_claude_only_workflow_references` enforces the pairing.

Spike (read-only): rendering every template blob from every template-changing commit (f8720ae, d679f8e, d761b50, 027bc84, 745c2be) into its vault path gives **25 distinct hashes over 10 paths**: `AGENTS.md` 3, `CLAUDE.md` 3 (2 full-schema, 1 stub), `.claude/commands/{ingest 4, lint 3, query 3}.md`, `.agents/skills/wiki-{ingest 3, lint 2, query 1}/SKILL.md`, `.claude/settings.json` 1, `.gitignore` 2. `render_workflow` has been unchanged since it was introduced in d761b50, so rendering old workflow blobs with it reproduces exactly what those versions wrote. Before d761b50, `.claude/commands/*.md` were verbatim copies of the templates.

## Goals / Non-Goals

**Goals:**
- One command that brings any vault ever created by this tool up to date, without ever losing a user edit.
- Leave the judgement part (merging customisations) to the agent, through a workflow.
- Keep `init` simple: it still never modifies files.

**Non-Goals:**
- An automatic 3-way merge engine.
- Upgrading `llmwiki.toml` or migrating vault content (pages, raw files). `layout_version` stays 1; a future layout change would need its own migration.
- Upgrading the tool itself (`git pull` and `pip install -e .` stay manual and documented).
- Keeping unprefixed command aliases. The rename is a clean break, handled by upgrade.

## Decisions

### D1. Registry: `templates/known_hashes.json`, maintained by a script, guarded by a test
- Format: `{"version": 1, "paths": {"<vault-rel-path>": ["<sha256>", ...]}}`. Hashes are sha256 of the UTF-8 content with `\r\n` normalised to `\n`.
- `scripts/known_hashes.py` (dev-only, not packaged): `--from-git` seeds the file from all history (the spike above); the default mode *adds* the current `planned_files()` hashes. Existing entries are never removed.
- A test fails if any current `planned_files()` output, or any path it produces, is missing from the registry, with the message "run `python scripts/known_hashes.py`". This makes it impossible to ship a template change that upgrade can't recognise later.
- **Obsolete paths** are computed, not stored: registry paths that `planned_files()` no longer produces.
- *Alternatives:* a manifest written into each vault (doesn't cover vaults created before this change, and adds state that can drift), or git blame in the vault (vaults aren't always git repos).

### D2. Managed set and planning
Managed paths are `planned_files()` keys except `llmwiki.toml` and `log.md`, plus the obsolete paths. `upgrade.plan(vault) -> list[Item]` is pure (it reads only the managed files) and classifies each file per the spec: `create`, `unchanged`, `update`, `conflict`, `delete`, `keep`. It also records whether a `<path>.new` exists (for status and lint). `upgrade.apply(vault, plan)` performs the writes. `--dry-run`, `wiki status` and `wiki lint` all reuse `plan()`, so they can't disagree. Writes use a temp file plus `os.replace`, so an interrupted upgrade never leaves a half-written file. `.new` files are written the same way.

### D3. Rename: Claude commands become `.claude/commands/wiki-<name>.md`
`render_workflow` changes its Claude output path from `.claude/commands/{name}.md` to `.claude/commands/wiki-{name}.md`, and its content stays identical. The old paths become obsolete automatically (registry path, no longer produced), so the upgrade deletes them when untouched. Kimi paths are unchanged. This touches:
- `AGENTS.md`: the Workflows table and cross-references use `/wiki-<name>` and `/skill:wiki-<name>`.
- The workflow bodies: the same references.
- `render_text`: `claude … /wiki-ingest`.
- The README.
- The test enforcing agent-neutral naming: every `/wiki-<name>` must sit next to `/skill:wiki-<name>`, and no unprefixed `/ingest|/query|/lint|/upgrade` may appear.

### D4. The `upgrade` workflow (`templates/workflows/upgrade.md`)
1. Run `wiki upgrade --dry-run --json`, summarise it, and wait for approval.
2. Run `wiki upgrade --json`.
3. For each `conflict`: read the user's file and `<path>.new`, and produce a merged version that keeps every user customisation and adopts new or changed template sections and rules. For `AGENTS.md`, keep the user's own sections verbatim. Show a diff (`git diff --no-index <path> <merged>` or a summary), apply it on approval, and delete `<path>.new`.
4. For each `kept` obsolete file, offer to merge its edits into the replacement path, then delete it.
5. Run `wiki lint --json`: no `template_merge_pending` should remain.
6. Commit with `upgrade: vault templates`.
7. Tell the human to restart the agent session so renamed commands load.

It never touches `raw/` or `wiki/`. With both agents, it's invoked as `/wiki-upgrade` and `/skill:wiki-upgrade`.

### D5. Git awareness
If `git -C <vault> rev-parse` succeeds and `git status --porcelain -- <managed paths>` is non-empty, warn: "uncommitted changes to template files; commit first so the upgrade can be reviewed or undone with git". The upgrade proceeds, because user edits are never overwritten anyway. If git is unavailable, skip this check.

### D6. Status and lint integration
- `wiki status` adds `templates: {outdated: [...], edited: [...], missing: [...], obsolete: [...], pending_merge: [...]}`, where `obsolete` counts both deletable and kept files. Text: `templates: up to date`, or `templates: 2 outdated, 1 edited, 3 obsolete - run wiki upgrade`.
- `wiki lint` adds `template_merge_pending` (info) for each existing `<managed path>.new`. It stays a no-fail info finding (exit 0 unless other errors), so a fresh vault still lints clean.

### D7. CLI output
`wiki upgrade --json` returns `{"vault", "dry_run", "items": [{"path", "action", "new_path"?, "replaced_by"?}], "counts": {...}}`, with warnings through `Outcome.warnings` (dirty git, kept obsolete files). The text output is one line per non-`unchanged` item plus a summary line, then "next: run the upgrade workflow (`/wiki-upgrade` or `/skill:wiki-upgrade`) to merge conflicts" when there are any. Exit code 0; conflicts are expected outcomes, not errors.

### D8. Verification and implementation notes (recorded during apply)
- **End-to-end, real CLI, rebuilt vaults** (built with `scripts/known_hashes.py`'s `historical_files()`):
  - (a) **first release (f8720ae)**: status before was `2 outdated, 9 missing, 3 obsolete - run wiki upgrade`. Upgrade: 9 created (`AGENTS.md`, four `wiki-*` commands and skills), 2 updated (`CLAUDE.md` becomes the `@AGENTS.md` stub, `.gitignore`), 3 deleted (`ingest.md`/`query.md`/`lint.md`, each reported as replaced by its `wiki-` path), 0 conflicts. Status after: `templates: up to date`. `wiki lint --strict`: 0/0/0.
  - (b) **agent-neutral release (d761b50) with an edited `AGENTS.md`**: `AGENTS.md` was reported as a conflict with `AGENTS.md.new` written. The user's added section was preserved and `.new` contains the new Authors section. 5 created, 2 updated (the Kimi `wiki-ingest`/`wiki-lint` skills), 3 deleted. Status after: `1 edited, 1 pending merge (AGENTS.md.new)`. Lint: exactly one `template_merge_pending` info, exit 0.
- **Registry:** seeded with `--from-git` and rebuilt from scratch at the end of the implementation, so it holds the 25 released hashes plus the current templates (32 in total), and none of the intermediate hashes from development edits.
- **History-era Claude paths:** `historical_files()` decides a commit's Claude command path by checking whether that commit's `scaffold.py` renders `.claude/commands/wiki-{name}`, so rendering the pre-rename history with the current renderer maps to the paths those versions actually wrote.
- **CI:** `actions/checkout` now uses `fetch-depth: 0`. Otherwise the tests that rebuild old vaults from git history would be skipped silently on shallow clones. They are marked `needs_history` and skip only when the history is really unavailable.
- **Naming rule enforced by test:** no unprefixed `/ingest|/query|/lint|/upgrade` may appear in the schema or workflows, and every `/wiki-X` must be paired with `/skill:wiki-X` on the same line. The upgrade workflow's final step therefore lists one pair per line.

## Risks / Trade-offs

- [A user's edited file coincidentally equals an old template] → then it *is* that template, and replacing it loses nothing.
- [A template changes without the registry being updated] → the D1 test fails in CI.
- [Line-ending or trailing-newline differences, e.g. an editor adding a final newline] → normalise only `\r\n`. A trailing newline added by an editor makes the file count as edited, which is the safe direction (a `.new` plus a merge).
- [An agent merge drops a user customisation] → the workflow requires showing the diff and getting approval, and git keeps both versions.
- [The rename breaks the user's muscle memory] → documented, and the agents' schema lists the new names. Upgrade removes the old files, so there's no confusing mix.
- [An interrupted upgrade] → atomic writes per file. Re-running is idempotent.

## Migration Plan

1. Update the tool (`git pull`, `pip install -e .`).
2. In each vault, run `wiki upgrade` once from the terminal. This creates `wiki-upgrade` for both agents, plus everything else.
3. Restart the agent and run `/wiki-upgrade` (or `/skill:wiki-upgrade`) to merge any conflicts.
4. Commit.

Rollback: `git checkout` the vault's template files.

## Open Questions

None.
