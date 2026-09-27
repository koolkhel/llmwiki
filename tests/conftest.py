"""Shared fixtures.

All test data here is synthetic. Never put real note titles or content in
this repository.
"""

from __future__ import annotations

import datetime as dt
import json
import socket
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

# --- Synthetic title corpus ------------------------------------------------
# Each entry exercises a property that matters for naming/link code.

NFD_TITLE = unicodedata.normalize("NFD", "Café Économie")  # combining accents
NFC_TITLE = unicodedata.normalize("NFC", NFD_TITLE)
EMOJI_TITLE = "Rocket 🚀 Notes 👩‍💻"  # includes a ZWJ sequence
CYRILLIC_TITLE = "Синтетическая заметка"
ILLEGAL_TITLE = 'A/B: "Test"?'
LINK_BREAKING_TITLE = "Heading # Block ^ref [x] | pipe"
LONG_CYRILLIC_TITLE = "Ж" * 300  # 600 UTF-8 bytes
CASE_DUPES = ("Transformers", "transformers")
ONLY_ILLEGAL_TITLE = "???"

SYNTHETIC_TITLES = [
    NFD_TITLE,
    EMOJI_TITLE,
    CYRILLIC_TITLE,
    ILLEGAL_TITLE,
    LINK_BREAKING_TITLE,
    LONG_CYRILLIC_TITLE,
    *CASE_DUPES,
]

TYPE_DIRS = {"source": "sources", "entity": "entities", "concept": "concepts", "analysis": "analyses"}


# --- Isolation --------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if anything tries to open a network connection."""

    def guard(*args, **kwargs):
        raise RuntimeError("network access attempted during tests")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


@pytest.fixture(autouse=True)
def _offline_tldextract(monkeypatch):
    """Use tldextract's bundled suffix snapshot instead of downloading one."""
    try:
        import tldextract
    except ImportError:  # pragma: no cover
        return
    offline = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)
    monkeypatch.setattr(tldextract, "extract", offline)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("LLMWIKI_VAULT", raising=False)


# --- Vault builders ---------------------------------------------------------


@dataclass
class VaultBuilder:
    root: Path

    def page(
        self,
        type_: str,
        title: str,
        body: str = "",
        summary: str = "",
        folder: str | None = None,
        **meta: object,
    ) -> Path:
        """Write a wiki page with valid frontmatter; returns its path."""
        folder = folder if folder is not None else TYPE_DIRS[type_]
        fm = {
            "type": type_,
            "summary": summary,
            "sources": [],
            "tags": [],
            "created": dt.date(2026, 1, 1),
            "updated": dt.date(2026, 1, 1),
        }
        fm.update(meta)
        path = self.root / "wiki" / folder / f"{title}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(fm, body), encoding="utf-8")
        return path

    def raw(self, name: str, body: str, **meta: object) -> Path:
        """Write a raw source file with the given frontmatter; returns its path."""
        import hashlib

        norm = body.replace("\r\n", "\n").strip("\n")
        fm = {"kind": "file", "title": name, "captured_at": "2026-01-01T00:00:00Z",
              "sha256": hashlib.sha256(norm.encode()).hexdigest()}
        fm.update(meta)
        path = self.root / "raw" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_dump(fm, norm + "\n"), encoding="utf-8")
        return path

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()


def _dump(meta: dict, body: str) -> str:
    y = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{y}---\n\n{body}"


@pytest.fixture
def tmp_vault(tmp_path) -> VaultBuilder:
    """A minimal vault layout (marker + folders), independent of `wiki init`."""
    root = tmp_path / "vault"
    for d in ("raw/.orig", *(f"wiki/{v}" for v in TYPE_DIRS.values())):
        (root / d).mkdir(parents=True)
    (root / "llmwiki.toml").write_text("layout_version = 1\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    return VaultBuilder(root)


# --- CLI runner ---------------------------------------------------------------


@dataclass
class CliResult:
    code: int
    out: str
    err: str

    def json(self) -> dict:
        return json.loads(self.out)


@pytest.fixture
def run_cli(capsys):
    from llmwiki.cli import main

    def run(*args: str) -> CliResult:
        capsys.readouterr()
        code = main([str(a) for a in args])
        captured = capsys.readouterr()
        return CliResult(code, captured.out, captured.err)

    return run
