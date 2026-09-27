## 1. Hash registry

- [x] 1.1 Add `scripts/known_hashes.py` with `--from-git` (render every template blob from every template-changing commit into vault paths, as in the design spike) and a default "add current `planned_files()` hashes" mode, writing `src/llmwiki/templates/known_hashes.json` (merge-only, sorted, `\r\n`-normalised). Run `--from-git`, then the default mode. Verify the JSON contains the spike's 25 historical hashes over 10 paths, plus the current ones.
- [x] 1.2 Add a registry-completeness test: every current `planned_files()` path and hash (except `llmwiki.toml`/`log.md`) is present. Verify it passes, and fails when a template is edited without re-running the script (checked with a temporary monkeypatched template).

## 2. Rename and upgrade workflow

- [x] 2.1 Change `render_workflow` to write `.claude/commands/wiki-<name>.md`. Update `AGENTS.md`, the workflow bodies, `render_text` and the README to `/wiki-<name>` and `/skill:wiki-<name>`. Update the agent-neutral reference test to the new rule (no unprefixed forms). Verify the init tests with the new expected paths.
- [x] 2.2 Add `templates/workflows/upgrade.md` per D4, rendered for both agents, and list it in `AGENTS.md`'s Workflows table. Verify init creates `.claude/commands/wiki-upgrade.md` and `.agents/skills/wiki-upgrade/SKILL.md` with identical bodies. Re-run `scripts/known_hashes.py` so the registry test passes.

## 3. Upgrade engine and CLI

- [x] 3.1 Implement `upgrade.plan()` and `upgrade.apply()` per D2/D5 (classification, atomic writes, `.new` handling, obsolete deletion or keeping, git-dirty warning), and `wiki upgrade [--dry-run] [--json]` per D7. Verify with tests for every spec scenario:
  - a bootstrap-era vault, built from `git show f8720ae:` template blobs into a temp dir, upgrades with the expected creates, updates and deletes;
  - edited `AGENTS.md` produces a conflict and `.new`;
  - edited obsolete `ingest.md` is kept with a warning;
  - dry run leaves the vault byte-identical;
  - content files stay byte-identical;
  - a second run is idempotent;
  - the dirty-git warning appears.

## 4. Status and lint

- [x] 4.1 Add the `templates` freshness report to `wiki status` (JSON and text) and the `template_merge_pending` info finding to lint per D6, both via `upgrade.plan()`. Verify with tests: outdated and obsolete are reported, a fresh vault reports nothing, a pending `.new` is reported by both, and a fresh vault still lints clean with `--strict`.

## 5. Docs and verification

- [x] 5.1 README: the new command names, `wiki upgrade`, `/wiki-upgrade`, and the "after updating the tool" steps (replacing the manual migration note). Verify by reading.
- [x] 5.2 End-to-end in scratch directories: (a) a bootstrap-era vault and (b) a vault created at d761b50 with an edited `AGENTS.md`, each upgraded with the current CLI. Check the reports, `wiki status` before and after, and `wiki lint --strict` (only `template_merge_pending` in b). Record the results in design.md.
