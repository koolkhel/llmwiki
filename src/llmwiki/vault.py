"""Vault discovery and layout."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import WikiError

MARKER = "llmwiki.toml"
ENV_VAR = "LLMWIKI_VAULT"
LAYOUT_VERSION = 1

# Page type -> folder under wiki/. Order is the canonical display order.
TYPE_DIRS: dict[str, str] = {
    "source": "sources",
    "entity": "entities",
    "concept": "concepts",
    "analysis": "analyses",
}
PAGE_TYPES = tuple(TYPE_DIRS)
DIR_TYPES = {v: k for k, v in TYPE_DIRS.items()}


@dataclass(frozen=True)
class Vault:
    root: Path

    @property
    def marker(self) -> Path:
        return self.root / MARKER

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def orig_dir(self) -> Path:
        return self.raw_dir / ".orig"

    @property
    def wiki_dir(self) -> Path:
        return self.root / "wiki"

    @property
    def index_path(self) -> Path:
        return self.root / "index.md"

    @property
    def log_path(self) -> Path:
        return self.root / "log.md"

    def type_dir(self, page_type: str) -> Path:
        return self.wiki_dir / TYPE_DIRS[page_type]

    def rel(self, path: Path) -> str:
        """Vault-relative POSIX path."""
        return path.resolve().relative_to(self.root).as_posix()


def _as_vault(path: Path, source: str) -> Vault:
    root = path.expanduser().resolve()
    if not (root / MARKER).is_file():
        raise WikiError(
            "not_a_vault",
            f"{root} (from {source}) is not a vault: no {MARKER} found. Run `wiki init {root}` first.",
            path=str(root),
        )
    return Vault(root)


def find_vault(
    explicit: Path | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Vault:
    """Locate the vault: --vault, then $LLMWIKI_VAULT, then nearest ancestor with the marker."""
    if explicit is not None:
        return _as_vault(Path(explicit), "--vault")
    env = os.environ if env is None else env
    if env.get(ENV_VAR):
        return _as_vault(Path(env[ENV_VAR]), f"${ENV_VAR}")
    start = (cwd or Path.cwd()).resolve()
    for d in (start, *start.parents):
        if (d / MARKER).is_file():
            return Vault(d)
    raise WikiError(
        "vault_not_found",
        f"No vault found: no {MARKER} in {start} or any parent. "
        f"Pass --vault <dir>, set ${ENV_VAR}, or run from inside a vault (create one with `wiki init <dir>`).",
    )
