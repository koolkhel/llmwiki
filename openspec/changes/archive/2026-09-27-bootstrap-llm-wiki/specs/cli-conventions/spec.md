## Purpose

Defines the behaviour every `wiki` command shares, so that Claude Code and humans can drive the CLI predictably: how a vault is located, how results and errors are reported, and what side effects are allowed.

## ADDED Requirements

### Requirement: Vault discovery
Every command other than `init` SHALL operate on a vault, located in this order: the `--vault <dir>` option, then the `LLMWIKI_VAULT` environment variable, then the nearest ancestor of the current directory (including itself) containing a `llmwiki.toml` marker file. If no vault is found the command SHALL fail without side effects.

#### Scenario: Run from a subdirectory of a vault
- **WHEN** the user runs `wiki status` from `<vault>/wiki/concepts/`
- **THEN** the command operates on `<vault>` because it contains `llmwiki.toml`

#### Scenario: Explicit option wins
- **WHEN** `LLMWIKI_VAULT` points to vault A and the user runs `wiki status --vault B`
- **THEN** the command operates on vault B

#### Scenario: No vault found
- **WHEN** the user runs `wiki lint` in a directory with no `llmwiki.toml` in it or any ancestor, and neither `--vault` nor `LLMWIKI_VAULT` is set
- **THEN** the command exits with code 2 and prints an error explaining how to specify a vault

### Requirement: Machine-readable output
Every command SHALL accept `--json`. With `--json`, the command SHALL write exactly one JSON document to stdout (success or error) and nothing else to stdout; human-oriented messages MAY go to stderr. Without `--json`, output SHALL be human-readable text.

#### Scenario: JSON success output
- **WHEN** the user runs `wiki status --json`
- **THEN** stdout contains a single parseable JSON object and no other text

#### Scenario: JSON error output
- **WHEN** a command run with `--json` fails
- **THEN** stdout contains a single JSON object with an `error` object holding a stable `code` string and a human-readable `message`

### Requirement: Exit codes
Commands SHALL exit with code 0 on success, 1 when the command ran but found problems it is reporting (for example lint errors), and 2 for usage errors, missing vault, invalid input, or operational failures (for example a failed fetch).

#### Scenario: Usage error
- **WHEN** the user runs `wiki add-source` with no argument
- **THEN** the command exits with code 2

### Requirement: Idempotent, bounded side effects
Commands SHALL only write inside the vault (or, for `init`, the target directory). Re-running a command with the same inputs against an unchanged vault SHALL NOT create duplicate files or entries, except for `wiki log`, which appends by design. No command SHALL access the network except `wiki add-source` given a URL.

#### Scenario: Re-running index
- **WHEN** the user runs `wiki index` twice without changing any page
- **THEN** `index.md` is byte-identical after the second run

#### Scenario: Offline operation
- **WHEN** the network is unavailable
- **THEN** every command except URL capture works normally

### Requirement: No external personal-notes access
The CLI SHALL NOT read from any notes application database or export (for example Joplin); its only inputs are the vault, files and URLs explicitly passed to it, and its own configuration.

#### Scenario: Only explicit inputs
- **WHEN** any command runs
- **THEN** it reads only files inside the vault, paths given as arguments, and the URL given to `add-source`
