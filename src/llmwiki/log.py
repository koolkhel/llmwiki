"""Append-only log.md with greppable `## [YYYY-MM-DD HH:MM] op | message` entries."""

from __future__ import annotations

import datetime as dt
import re

from .errors import WikiError
from .vault import Vault

OPERATIONS = ("ingest", "query", "lint", "init", "note")
_HEADING = re.compile(r"^## \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] .*$", re.M)


def _one_line(s: str) -> str:
    return " ".join(s.split())


def append(vault: Vault, op: str, message: str, detail: str | None = None, now: dt.datetime | None = None) -> dict:
    if op not in OPERATIONS:
        raise WikiError("invalid_operation", f"Operation must be one of: {', '.join(OPERATIONS)}.")
    message = _one_line(message)
    if not message:
        raise WikiError("empty_message", "Log message must not be empty.")
    stamp = (now or dt.datetime.now().astimezone()).strftime("%Y-%m-%d %H:%M")
    heading = f"## [{stamp}] {op} | {message}"
    entry = f"\n{heading}\n"
    if detail and detail.strip():
        entry += f"\n{detail.strip()}\n"
    path = vault.log_path
    prefix = ""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as f:
            f.seek(-1, 2)
            if f.read(1) != b"\n":
                prefix = "\n"
    with path.open("a", encoding="utf-8") as f:  # append only; never rewritten
        f.write(prefix + entry)
    return {"path": vault.rel(path), "entry": heading}


def last_heading(vault: Vault) -> str | None:
    try:
        text = vault.log_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    found = _HEADING.findall(text)
    return found[-1] if found else None
