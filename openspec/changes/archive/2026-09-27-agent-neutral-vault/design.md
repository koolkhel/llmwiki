## Context

See proposal.md for motivation. Current state:
- `scaffold.py` copies `templates/vault/` verbatim. Path parts named `dot-x` are installed as `.x`, and `{{layout_version}}`/`{{date}}` are filled in. It never overwrites, and it reports created and skipped files.
- The templates are `CLAUDE.md` (the full schema), `dot-claude/commands/{ingest,query,lint}.md` (frontmatter `description` and `argument-hint`, then a body using `$ARGUMENTS`), `dot-claude/settings.json`, `dot-gitignore`, `llmwiki.toml` and `log.md`.
- Claude-only references: the schema's Workflows section lists `/ingest`, `/query` and `/lint`; each workflow body says "following `CLAUDE.md`"; `lint.md` offers to "`/ingest`" pending sources; `scaffold.render_text` suggests `claude … /ingest`; the README.

Probe results (Kimi Code 2.1.1, throwaway vault, run by the user):

| Check | Result |
|---|---|
| `AGENTS.md` loaded as project instructions | yes (canary answered) |
| `.agents/skills/<name>/SKILL.md` discovered, `/skill:<name>` listed | yes |
| `$ARGUMENTS` expanded in a skill | yes |
| `[[permission.rules]]` in `.kimi-code/local.toml` | **ignored**: even `Bash(ls*)` still prompted. `kimi doctor` doesn't check this file |
| Tool names | `Write`, `Edit`, `Bash` |
| Ask When Needed with `AGENTS.md` forbidding `raw/` edits | refused both a direct append and a "fix this typo" request, citing `AGENTS.md`; `wiki status` ran without prompting |
| Instruction wording | Kimi suggested "`/ingest`", taken from the Claude-oriented schema, which is why neutral naming is needed |

## Goals / Non-Goals

**Goals:**
- One vault that works equally well in Claude Code and Kimi Code, with a single schema and a single workflow text.
- No behaviour change for Claude Code users beyond where the schema file lives.

**Non-Goals:**
- Enforcing `raw/` immutability in Kimi Code (not possible per project, see the probe). Lint and git remain the backstop.
- Automatically migrating existing vaults (the sandbox is the only one; a warning is enough).
- Other agents (Codex, Cursor, …). `AGENTS.md` plus `.agents/skills/` probably helps them too, but that is untested and not claimed.
- Writing to the user's global Kimi config, or setting up Kimi's global privacy instructions (the user's responsibility).

## Decisions

### D1. `AGENTS.md` is the schema; `CLAUDE.md` is `@AGENTS.md`
Claude Code expands `@path` imports inside `CLAUDE.md`, so a `CLAUDE.md` that holds only the import line gives Claude the full schema while the user edits a single file. *Alternatives:* relying on Claude Code's own `AGENTS.md` fallback (depends on version and settings, and is ignored whenever any `CLAUDE.md` exists), or keeping two copies (they drift apart). The template `CLAUDE.md` holds a one-line comment explaining the import, followed by `@AGENTS.md`.

### D2. One workflow template, two renderings
New template directory `templates/workflows/{ingest,query,lint}.md`. Each file has frontmatter (`description`, `argument-hint`) and a body. `scaffold.py` renders each one as:
- `.claude/commands/<name>.md`: frontmatter `description` and `argument-hint`, then the body.
- `.agents/skills/wiki-<name>/SKILL.md`: frontmatter `name: wiki-<name>` and `description`, then the body.

The bodies are byte-identical (a test asserts this). `$ARGUMENTS` works in both agents. The `dot-claude/commands/` templates are removed. `template_files()` and the created/skipped report include the rendered paths. The never-overwrite rule applies to each rendered file on its own. *Alternatives:* two hand-maintained copies (they drift), or symlinks (break on some filesystems and in git on Windows, and a symlinked `SKILL.md` would still need different frontmatter).

### D3. Skills go in `.agents/skills/`, not `.kimi-code/skills/`
`.agents/` is Kimi's cross-agent directory (confirmed by the probe) and doesn't tie the vault to one vendor's folder name. The `wiki-` prefix avoids colliding with a user's global skills called `ingest` or similar.

### D4. Agent-neutral workflow naming
The schema's Workflows section becomes a small table: workflow, Claude Code invocation, Kimi Code invocation, purpose. Workflow bodies say "following `AGENTS.md`", and cross-references read "the **ingest** workflow (`/ingest` in Claude Code, `/skill:wiki-ingest` in Kimi Code)". A test scans the rendered schema and bodies for any bare `/ingest`, `/query` or `/lint` that isn't followed by its Kimi form.

### D5. Permissions
- Claude Code keeps `.claude/settings.json` as it is.
- Kimi Code gets no permission file (the probe showed project rules are ignored). `.kimi-code/local.toml` is added to the vault `.gitignore`, because Kimi's docs describe it as holding machine-specific paths.
- The README gets a "Using Kimi Code" section with a protection table: Always Ask means the user approves every write; Ask When Needed means the model follows `AGENTS.md`, as observed in the probe; Never Ask/`--auto` means only the model. In every mode, `wiki lint` reports `raw_modified` and git restores the file.

### D6. Legacy-schema warning
In `init_vault`, if `CLAUDE.md` existed before the run and does not contain the line `@AGENTS.md`, append a warning: "CLAUDE.md predates the shared AGENTS.md schema. Merge any customisations into AGENTS.md, then replace CLAUDE.md with the single line `@AGENTS.md`." The detection is a plain line check. The file is never modified.

### D7. Verification result (recorded during apply)
In a fresh vault initialised by the new `wiki init`, both Claude Code and Kimi Code listed all three workflows (`/ingest`, `/query`, `/lint` and `/skill:wiki-ingest`, `/skill:wiki-query`, `/skill:wiki-lint`). Asked "Without reading any files, answer from your instructions only: where do raw sources live in this vault, which command is allowed to write there, and may you edit them?", both answered `raw/` (with `raw/.orig/`), only `wiki add-source`, and never edit. Kimi said the `AGENTS.md` content was in its system prompt. Claude paraphrased the new agent-neutral web-fetch sentence, which exists only in the new `AGENTS.md`, confirming that the `@AGENTS.md` import in `CLAUDE.md` works.

## Risks / Trade-offs

- [Claude Code changes or drops `@` imports in `CLAUDE.md`] → this is documented Claude Code behaviour and is covered by a manual check in the tasks. If it ever broke, Claude's `AGENTS.md` fallback would still apply once `CLAUDE.md` is removed.
- [Kimi's model obeying `AGENTS.md` is behaviour, not enforcement] → documented as such, with lint and git as the backstop. The user runs Always Ask anyway.
- [A skill name collides with a user-level `wiki-*` skill] → Kimi gives project skills precedence over user skills. The prefix keeps collisions unlikely.
- [Existing vaults end up with the schema in two places after re-init] → the warning, plus a README migration note.

## Migration Plan

For an existing vault: run `wiki init <vault>`, which adds `AGENTS.md` and `.agents/skills/…` and warns about `CLAUDE.md`. Then merge any customisations from `CLAUDE.md` into `AGENTS.md`, and replace `CLAUDE.md` with the line `@AGENTS.md`. Older `.claude/commands/*.md` files are left as they were; delete them and re-run `wiki init` to get the neutral wording. Rolling back means re-running an older `wiki init` in a fresh directory, since there is no data impact.

## Open Questions

None.
