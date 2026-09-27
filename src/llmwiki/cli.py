"""`wiki` command-line interface.

Every command accepts `--json` (exactly one JSON document on stdout) and,
except `init`, `--vault`. Exit codes: 0 ok, 1 problems reported, 2 errors.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import index, lint, log, pages, scaffold, search, sources, status
from .errors import EXIT_ERROR, WikiError
from .vault import find_vault

try:  # Typer >= 0.2x vendors click; its exceptions are not re-exported publicly.
    from typer._click.exceptions import UsageError as _UsageError
except ImportError:  # pragma: no cover - older Typer uses the click package
    from click import UsageError as _UsageError

app = typer.Typer(
    name="wiki",
    help="Deterministic bookkeeping for an LLM-maintained markdown wiki.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

JsonOpt = Annotated[bool, typer.Option("--json", help="Write a single JSON document to stdout.")]
VaultOpt = Annotated[
    Optional[Path],
    typer.Option(
        "--vault",
        help="Vault directory. Default: $LLMWIKI_VAULT, else the nearest ancestor containing llmwiki.toml.",
        show_default=False,
    ),
]


@dataclass
class Outcome:
    """What a command produced: JSON data, human text, and an exit code."""

    data: dict
    text: str
    exit_code: int = 0
    warnings: list[str] = field(default_factory=list)


def _print_json(obj: object) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")


def run(as_json: bool, fn: Callable[[], Outcome]) -> None:
    """Run a command body and report its outcome in the requested format."""
    try:
        outcome = fn()
    except WikiError as e:
        if as_json:
            _print_json(e.to_dict())
        else:
            typer.echo(f"error: {e.message}", err=True)
        raise typer.Exit(EXIT_ERROR)
    if as_json:
        data = dict(outcome.data)
        if outcome.warnings:
            data["warnings"] = outcome.warnings
        _print_json(data)
    else:
        if outcome.text:
            typer.echo(outcome.text)
        for w in outcome.warnings:
            typer.echo(f"warning: {w}", err=True)
    if outcome.exit_code:
        raise typer.Exit(outcome.exit_code)


@app.callback()
def _root() -> None:
    """Deterministic bookkeeping for an LLM-maintained markdown wiki."""


@app.command("init")
def init_cmd(
    directory: Annotated[Path, typer.Argument(help="Vault directory to create or complete.")],
    no_git: Annotated[bool, typer.Option("--no-git", help="Do not run `git init`.")] = False,
    json_: JsonOpt = False,
) -> None:
    """Scaffold a vault: layout, CLAUDE.md schema, Claude Code commands. Never overwrites files."""

    def body() -> Outcome:
        res, warnings = scaffold.init_vault(directory, git=not no_git)
        return Outcome(res, scaffold.render_text(res), warnings=warnings)

    run(json_, body)


class PageType(str, Enum):
    source = "source"
    entity = "entity"
    concept = "concept"
    analysis = "analysis"


@app.command("add-source")
def add_source_cmd(
    source: Annotated[str, typer.Argument(help="An http(s) URL, or a path to a UTF-8 .txt/.md file.")],
    json_: JsonOpt = False,
    vault: VaultOpt = None,
) -> None:
    """Capture a URL or text file into raw/ (immutable, with provenance frontmatter)."""

    def body() -> Outcome:
        res = sources.capture(find_vault(vault), source)
        if res["duplicate_of"]:
            text = f"already captured: {res['duplicate_of']} ({res['status']})"
        else:
            text = f"captured {res['path']} ({res['status']})"
        return Outcome(res, text)

    run(json_, body)


@app.command("new-page")
def new_page_cmd(
    title: Annotated[str, typer.Argument(help="Page title; becomes the filename.")],
    type_: Annotated[PageType, typer.Option("--type", help="Page type (decides the folder).")],
    raw: Annotated[
        Optional[str], typer.Option("--raw", help="For source pages: the raw/ file this page summarises.")
    ] = None,
    json_: JsonOpt = False,
    vault: VaultOpt = None,
) -> None:
    """Create a wiki page whose filename is its title (never overwrites)."""

    def body() -> Outcome:
        res = pages.create_page(find_vault(vault), type_.value, title, raw=raw)
        return Outcome(res, f"created {res['path']}\nlink: {res['link']}")

    run(json_, body)


class LogOp(str, Enum):
    ingest = "ingest"
    query = "query"
    lint = "lint"
    init = "init"
    note = "note"


@app.command("index")
def index_cmd(json_: JsonOpt = False, vault: VaultOpt = None) -> None:
    """Regenerate index.md from the wiki pages."""

    def body() -> Outcome:
        res = index.write(find_vault(vault))
        verb = "updated" if res["changed"] else "unchanged"
        return Outcome(res, f"{verb} {res['path']} ({res['pages']} pages)")

    run(json_, body)


@app.command("log")
def log_cmd(
    operation: Annotated[LogOp, typer.Argument(help="Kind of activity.")],
    message: Annotated[str, typer.Argument(help="One-line description (e.g. the source title).")],
    detail: Annotated[Optional[str], typer.Option("--detail", help="Optional paragraph under the entry.")] = None,
    json_: JsonOpt = False,
    vault: VaultOpt = None,
) -> None:
    """Append an entry to log.md (append-only)."""

    def body() -> Outcome:
        res = log.append(find_vault(vault), operation.value, message, detail)
        return Outcome(res, res["entry"])

    run(json_, body)


@app.command("search")
def search_cmd(
    query: Annotated[list[str], typer.Argument(help="Search terms (all must match).")],
    type_: Annotated[Optional[PageType], typer.Option("--type", help="Only pages of this type.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum results.")] = 20,
    raw: Annotated[bool, typer.Option("--raw", help="Search raw sources instead of wiki pages.")] = False,
    exact: Annotated[
        bool, typer.Option("--exact", help="Whole words only: no word-form (lemma/stem) or substring matching.")
    ] = False,
    json_: JsonOpt = False,
    vault: VaultOpt = None,
) -> None:
    """Find pages by title, summary, tags and body. Matches word forms (кошка ~ кошек, run ~ running)."""

    def body() -> Outcome:
        res, warnings = search.search(
            find_vault(vault), " ".join(query), type_.value if type_ else None, limit, raw, exact
        )
        lines = [f"{r['link']}  ({r['type']}, {r['match']}, {r['path']})\n    {r['snippet']}" for r in res["results"]]
        shown = f"{len(res['results'])} of {res['total']}" if res["total"] > len(res["results"]) else str(res["total"])
        return Outcome(res, "\n".join([*lines, f"{shown} result(s)"]), warnings=warnings)

    run(json_, body)


@app.command("lint")
def lint_cmd(
    strict: Annotated[bool, typer.Option("--strict", help="Also fail (exit 1) on warnings.")] = False,
    json_: JsonOpt = False,
    vault: VaultOpt = None,
) -> None:
    """Structural health check (read-only). Exits 1 if errors are found."""

    def body() -> Outcome:
        data, code = lint.report(find_vault(vault), strict)
        return Outcome(data, lint.render_text(data), exit_code=code)

    run(json_, body)


@app.command("status")
def status_cmd(json_: JsonOpt = False, vault: VaultOpt = None) -> None:
    """Summarise the vault: page counts, pending sources, index freshness, last log entry."""

    def body() -> Outcome:
        res = status.vault_status(find_vault(vault))
        return Outcome(res, status.render_text(res))

    run(json_, body)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    as_json = "--json" in argv
    try:
        rv = app(args=argv, standalone_mode=False, prog_name="wiki")
    except _UsageError as e:
        if as_json:
            _print_json({"error": {"code": "usage_error", "message": e.format_message()}})
        else:
            e.show()
        return EXIT_ERROR
    except typer.Abort:
        return EXIT_ERROR
    except Exception as e:  # unexpected: keep the JSON contract, show traceback on stderr
        traceback.print_exc()
        if as_json:
            _print_json({"error": {"code": "internal_error", "message": f"{type(e).__name__}: {e}"}})
        return EXIT_ERROR
    return rv if isinstance(rv, int) else 0


def entrypoint() -> None:
    sys.exit(main())
