## 1. Templates

- [x] 1.1 Move the schema template from `templates/vault/CLAUDE.md` to `templates/vault/AGENTS.md`, making every workflow reference agent-neutral per D4 (a Workflows table with both invocations). Add a new `templates/vault/CLAUDE.md` containing an explanatory comment plus `@AGENTS.md`. Verify that grepping the templates finds no bare `/ingest`, `/query` or `/lint` without its Kimi form.
- [x] 1.2 Create `templates/workflows/{ingest,query,lint}.md` from the current command templates: frontmatter `description`/`argument-hint`, bodies saying "following `AGENTS.md`", and neutral cross-references (e.g. `lint` offering to run the ingest workflow). Remove `templates/vault/dot-claude/commands/`. Verify with `ls` that the old directory is gone and the three workflow templates exist.
- [x] 1.3 Add `.kimi-code/local.toml` to `templates/vault/dot-gitignore`. Verify with grep.

## 2. Scaffold

- [x] 2.1 Render each workflow template in `scaffold.py` into `.claude/commands/<name>.md` and `.agents/skills/wiki-<name>/SKILL.md` per D2, applying never-overwrite per file and including them in the created/skipped report and in `template_files()`. Verify with tests that a fresh init creates all 6 files, that the bodies are byte-identical per workflow, that the SKILL.md frontmatter has `name: wiki-<name>` and `description`, and that re-init skips existing rendered files.
- [x] 2.2 Add the D6 legacy-schema warning. Verify with tests that a pre-change vault (full `CLAUDE.md`, no `AGENTS.md`) gets `AGENTS.md` created, `CLAUDE.md` unchanged and skipped, and a warning, and that a `CLAUDE.md` containing `@AGENTS.md` produces no warning.
- [x] 2.3 Make the `render_text` "next:" hint mention both agents (`claude` → `/ingest …`, `kimi` → `/skill:wiki-ingest …`). Verify that text-mode init output contains both.

## 3. Tests and docs

- [x] 3.1 Update `tests/test_init.py` for the new layout: expected file list, the raw-immutability assertion moved to `AGENTS.md`, `CLAUDE.md` being only the import, no files under `.kimi-code/`, and the `.gitignore` entry. Add a test scanning the rendered `AGENTS.md` and workflow bodies for bare Claude-only workflow references. Verify that the full suite passes.
- [x] 3.2 Update the README: the schema lives in `AGENTS.md`; a "Using Kimi Code" section with invocations and the protection-by-mode table (D5); and a migration note for existing vaults. Verify by reading the rendered section.

## 4. Verification

- [x] 4.1 Wheel check: a non-editable install into a scratch venv lists `AGENTS.md`, `CLAUDE.md` and the workflow templates in the package. `wiki init` there creates the 6 workflow files, and `wiki lint --strict` on the fresh vault exits 0.
- [x] 4.2 Manual check (user): in a fresh vault, Claude Code shows `/ingest`, `/query` and `/lint` and knows the schema (it can answer where raw sources live); Kimi Code lists `/skill:wiki-ingest`, `/skill:wiki-query` and `/skill:wiki-lint` and loads `AGENTS.md`. Record the result.
