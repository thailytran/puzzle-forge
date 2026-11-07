"""SQLite registry of every puzzle ever produced (golden rule 4: no duplicates)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from forge.core.hashing import canonical_json
from forge.core.models import Puzzle

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS puzzles (
    content_hash TEXT PRIMARY KEY,
    puzzle_id    TEXT NOT NULL,
    type         TEXT NOT NULL,
    book_id      TEXT NOT NULL,
    seed         INTEGER NOT NULL,
    level        TEXT NOT NULL,
    data_json    TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_puzzles_book ON puzzles(book_id);
CREATE INDEX IF NOT EXISTS idx_puzzles_type ON puzzles(type);
"""


class DuplicatePuzzleError(Exception):
    def __init__(self, content_hash: str, existing_book: str) -> None:
        super().__init__(f"puzzle {content_hash[:12]} already used in book {existing_book!r}")
        self.content_hash = content_hash
        self.existing_book = existing_book


@dataclass(frozen=True)
class RegistryEntry:
    content_hash: str
    puzzle_id: str
    type: str
    book_id: str
    seed: int
    level: str
    created_at: str


class Registry:
    """Thin wrapper around a SQLite file. Use as a context manager."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(_SCHEMA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def __enter__(self) -> Registry:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def _book_of(self, content_hash: str) -> str | None:
        row = self._conn.execute(
            "SELECT book_id FROM puzzles WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return None if row is None else str(row[0])

    def owner(self, content_hash: str) -> str | None:
        """Book that registered this puzzle, if any."""
        return self._book_of(content_hash)

    def contains(self, content_hash: str) -> bool:
        return self._book_of(content_hash) is not None

    def add(self, puzzle: Puzzle, book_id: str) -> None:
        """Register a puzzle. Re-adding to the same book is a no-op; another book raises."""
        existing = self._book_of(puzzle.content_hash)
        if existing == book_id:
            return
        if existing is not None:
            raise DuplicatePuzzleError(puzzle.content_hash, existing)
        self._conn.execute(
            "INSERT INTO puzzles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                puzzle.content_hash,
                puzzle.id,
                puzzle.type,
                book_id,
                puzzle.seed,
                puzzle.spec.level,
                canonical_json(puzzle.data),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        self._conn.commit()

    def try_add(self, puzzle: Puzzle, book_id: str) -> bool:
        """Like `add` but returns False instead of raising on a duplicate."""
        try:
            self.add(puzzle, book_id)
        except DuplicatePuzzleError:
            return False
        return True

    def list_by_book(self, book_id: str) -> list[RegistryEntry]:
        rows = self._conn.execute(
            "SELECT content_hash, puzzle_id, type, book_id, seed, level, created_at "
            "FROM puzzles WHERE book_id = ? ORDER BY rowid",
            (book_id,),
        ).fetchall()
        return [RegistryEntry(*row) for row in rows]

    def remove_book(self, book_id: str) -> int:
        """Forget all puzzles of a book (e.g. a discarded draft). Returns rows deleted."""
        cur = self._conn.execute("DELETE FROM puzzles WHERE book_id = ?", (book_id,))
        self._conn.commit()
        return cur.rowcount

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT type, COUNT(*) FROM puzzles GROUP BY type ORDER BY type"
        ).fetchall()
        return {str(t): int(n) for t, n in rows}

    def books(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT book_id FROM puzzles ORDER BY book_id")
        return [str(r[0]) for r in rows.fetchall()]
