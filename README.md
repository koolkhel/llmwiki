# llmwiki

A small, deterministic Python CLI (`wiki`) for the
[LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
an LLM incrementally maintains a persistent, cross-linked markdown wiki built
from curated raw sources.

The split of responsibilities:

- **Claude Code is the brain.** It reads sources, writes and updates wiki
  pages, and spots contradictions, guided by the vault's `CLAUDE.md` and its
  `/ingest`, `/query` and `/lint` slash commands.
- **`wiki` is the bookkeeper.** It captures sources, names pages, resolves
  links, lints structure, and generates `index.md` and `log.md`. It never
  calls an LLM and needs no API key.
- **Obsidian is the viewer.** Vaults use `[[wikilinks]]` and YAML frontmatter.

This repository contains only the tool. Vaults are separate, private
directories.

## Install

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
mkdir -p ~/.local/bin && ln -sf "$PWD/.venv/bin/wiki" ~/.local/bin/wiki   # make `wiki` callable from vaults
wiki --help
```

## Use

```bash
wiki init ~/wikis/research          # scaffold a vault (git init, CLAUDE.md, slash commands)
cd ~/wikis/research && claude       # then: /ingest https://example.org/some-article
```

Open the same directory in Obsidian to browse it.

| Command | Purpose |
|---|---|
| `wiki init <dir>` | Scaffold a vault. Never overwrites existing files. |
| `wiki add-source <url\|file>` | Capture a URL or `.txt`/`.md` file into immutable `raw/`. |
| `wiki new-page --type T "Title"` | Create a page whose filename is its title. |
| `wiki search <terms>` | Find pages (or raw sources with `--raw`). Matches Russian and English word forms; `--exact` for literal words. |
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
