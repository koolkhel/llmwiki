"""Disposable per-vault cache of word form -> lemma/stem keys.

Lives in `.llmwiki/cache/lemmas.sqlite`, ignores itself in git, and is safe
to delete: it only saves recomputation. Every failure degrades to "no cache".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .morph import versions
from .vault import Vault

CACHE_DIR = Path(".llmwiki") / "cache"
DB_NAME = "lemmas.sqlite"
_SEP = " "  # keys are single words, so a space never occurs inside one


class LemmaCache:
    def __init__(self, vault: Vault) -> None:
        self.dir = vault.root / CACHE_DIR
        self.path = self.dir / DB_NAME
        self.version = versions()
        self.warnings: list[str] = []

    def _warn(self, action: str, err: Exception) -> None:
        self.warnings.append(
            f"search cache unavailable ({action}: {err}); continuing without it. "
            f"It is safe to delete {self.dir}."
        )

    def _connect(self) -> sqlite3.Connection:
        self.dir.mkdir(parents=True, exist_ok=True)
        ignore = self.dir / ".gitignore"
        if not ignore.exists():
            ignore.write_text("# Disposable search cache; safe to delete.\n*\n", encoding="utf-8")
        con = sqlite3.connect(self.path, timeout=5)
        con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS forms (form TEXT PRIMARY KEY, keys TEXT NOT NULL)")
        return con

    def load(self) -> dict[str, frozenset[str]]:
        if not self.path.exists():
            return {}
        try:
            con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=5)
            try:
                row = con.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
                if not row or row[0] != self.version:
                    return {}  # stale: rebuilt on save
                return {f: frozenset(k.split(_SEP)) for f, k in con.execute("SELECT form, keys FROM forms")}
            finally:
                con.close()
        except (sqlite3.Error, OSError) as e:
            self._warn("read", e)
            return {}

    def save(self, new: dict[str, frozenset[str]]) -> None:
        if not new and self.path.exists():
            return
        try:
            con = self._connect()
            try:
                with con:
                    row = con.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
                    if not row or row[0] != self.version:
                        con.execute("DELETE FROM forms")
                        con.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (self.version,))
                    con.executemany(
                        "INSERT OR REPLACE INTO forms VALUES (?, ?)",
                        ((f, _SEP.join(sorted(k))) for f, k in new.items()),
                    )
            finally:
                con.close()
        except (sqlite3.Error, OSError) as e:
            self._warn("write", e)
