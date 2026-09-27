# llmwiki

[![tests](https://github.com/koolkhel/llmwiki/actions/workflows/test.yml/badge.svg)](https://github.com/koolkhel/llmwiki/actions/workflows/test.yml)

A small, deterministic Python CLI (`wiki`) for the
[LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
an LLM incrementally maintains a persistent, cross-linked markdown wiki built
from curated raw sources.

The split of responsibilities:

- **A coding agent is the brain.** Claude Code or Kimi Code reads sources,
  writes and updates wiki pages, and spots contradictions, guided by the vault's
  `AGENTS.md` schema and its ingest, query and lint workflows.
- **`wiki` is the bookkeeper.** It captures sources, names pages, resolves
  links, lints structure, and generates `index.md` and `log.md`. It never
  calls an LLM and needs no API key.
- **Obsidian is the viewer.** Vaults use `[[wikilinks]]` and YAML frontmatter.

This repository contains only the tool. Vaults are separate, private
directories.

## Install

Requires Python 3.12 or newer. On Python 3.14, `lxml` (pinned below 6 by the
extractor stack) has no prebuilt wheels and is compiled during install: on
Linux, install `libxml2-dev` and `libxslt1-dev` first. macOS works out of the box.

```bash
git clone https://github.com/koolkhel/llmwiki.git && cd llmwiki
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
mkdir -p ~/.local/bin && ln -sf "$PWD/.venv/bin/wiki" ~/.local/bin/wiki   # make `wiki` callable from vaults
wiki --help
```

## Use

```bash
wiki init ~/wikis/research          # scaffold a vault (git init, AGENTS.md schema, workflows)
cd ~/wikis/research && claude       # Claude Code: /ingest https://example.org/some-article
cd ~/wikis/research && kimi         # Kimi Code:   /skill:wiki-ingest https://example.org/some-article
```

Open the same directory in Obsidian to browse it.

## Agents

A vault works with both agents at once. The schema is `AGENTS.md`, and
`CLAUDE.md` only imports it (`@AGENTS.md`), so there is one file to edit.
Each workflow is written from one template for both agents:

| Workflow | Claude Code | Kimi Code |
|---|---|---|
| ingest | `/ingest <url\|file>` | `/skill:wiki-ingest <url\|file>` |
| query | `/query <question>` | `/skill:wiki-query <question>` |
| lint | `/lint` | `/skill:wiki-lint` |

Files: `.claude/commands/*.md` for Claude Code, `.agents/skills/wiki-*/SKILL.md`
for Kimi Code.

### How `raw/` is protected

`raw/` holds the faithful copies of your sources and must never be edited.

| Agent / mode | Guard |
|---|---|
| Claude Code | `.claude/settings.json` denies edits under `raw/`, `index.md` and `log.md`. |
| Kimi Code, Always Ask | You approve every write and see the diff first. |
| Kimi Code, Ask When Needed | The model follows `AGENTS.md`; in testing it refused edits to `raw/`. |
| Kimi Code, Never Ask / `--auto` | The model only. |

Kimi Code ignores project-level permission rules (`.kimi-code/local.toml`), so
`wiki init` writes none. In every case, `wiki lint` reports `raw_modified` if a
raw file changes after capture, and `git checkout -- raw/` restores it.

### Migrating an older vault

Vaults created before `AGENTS.md` keep their full schema in `CLAUDE.md`. Run
`wiki init <vault>`: it adds `AGENTS.md` and the Kimi skills, leaves your files
untouched, and warns about `CLAUDE.md`. Then merge any customisations from
`CLAUDE.md` into `AGENTS.md`, and replace `CLAUDE.md` with the single line
`@AGENTS.md`. To get the updated workflow wording in `.claude/commands/`, delete
those files and run `wiki init` again.

| Command | Purpose |
|---|---|
| `wiki init <dir>` | Scaffold a vault. Never overwrites existing files. |
| `wiki add-source <url\|file>` | Capture a URL, a `.txt`/`.md` file, or a browser-saved `.html` page (`--url` to set its address) into immutable `raw/`. |
| `wiki new-page --type T "Title"` | Create a page whose filename is its title. |
| `wiki search <terms>` | Find pages (or raw sources with `--raw`). Matches Russian and English word forms; `--exact` for literal words; `--author <name>` for everything by a person. |
| `wiki source-meta <raw>\|--all` | Re-derive metadata (e.g. authors) from stored originals; `--all` lists sources whose source page lacks authors. Read-only. |
| `wiki index` | Regenerate `index.md`. |
| `wiki log <op> <message>` | Append to `log.md`. |
| `wiki lint [--strict]` | Structural health check. |
| `wiki status` | Vault summary, including sources pending ingestion. |

Every command accepts `--json`, which writes exactly one JSON document to
stdout. Exit codes are 0 (ok), 1 (problems reported, e.g. lint errors) and
2 (usage or operational error). The vault is taken from `--vault`, then
`$LLMWIKI_VAULT`, then the nearest ancestor directory containing
`llmwiki.toml`.

## Develop

```bash
.venv/bin/pytest
```

Tests use synthetic fixtures only and never touch the network.

### Spec-driven with OpenSpec

The project is developed with [OpenSpec](https://github.com/Fission-AI/OpenSpec),
a spec-driven workflow for AI coding assistants. Behaviour is written down as
requirements with testable scenarios before it is implemented:

- `openspec/specs/`: the current specs, one per capability (`cli-conventions`,
  `vault-init`, `source-capture`, `page-naming`, `wiki-lint`, `wiki-navigation`).
- `openspec/changes/archive/`: every completed change, with its proposal,
  design (including decisions, spike results and measurements), delta specs
  and task list.

A change goes explore → propose → apply → archive. Archiving merges the
change's delta specs into `openspec/specs/`. The workflows are installed for
both agents:

| Step | Claude Code | Kimi Code |
|---|---|---|
| Think it through | `/opsx:explore` | `/skill:openspec-explore` |
| Write proposal, specs, design, tasks | `/opsx:propose <name>` | `/skill:openspec-propose <name>` |
| Implement the tasks | `/opsx:apply` | `/skill:openspec-apply-change` |
| Sync specs and archive | `/opsx:archive` | `/skill:openspec-archive-change` |

The `openspec` CLI (`npm install -g @fission-ai/openspec`) provides
`openspec list`, `openspec show <spec>` and `openspec validate`.

## License

MIT. See [LICENSE](LICENSE).
