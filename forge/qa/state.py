"""Book state machine with append-only history (SQLite, same db as the registry)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Literal

State = Literal[
    "DRAFT",
    "QA_RUNNING",
    "QA_FAILED",
    "QA_PASSED",
    "SKU_ASSIGNED",
    "METADATA_READY",
    "MANUAL_REVIEW",
    "APPROVED",
    "REJECTED",
    "MARKETING_READY",
]

TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"QA_RUNNING"},
    "QA_RUNNING": {"QA_PASSED", "QA_FAILED"},
    "QA_FAILED": {"QA_RUNNING", "DRAFT"},  # auto-fix round re-runs QA
    "QA_PASSED": {"SKU_ASSIGNED", "DRAFT"},
    "SKU_ASSIGNED": {"METADATA_READY", "DRAFT"},
    "METADATA_READY": {"MANUAL_REVIEW", "DRAFT"},
    "MANUAL_REVIEW": {"APPROVED", "REJECTED", "DRAFT"},
    "REJECTED": {"DRAFT"},
    "APPROVED": {"MARKETING_READY", "DRAFT"},
    "MARKETING_READY": {"DRAFT"},
}
# → DRAFT from any later state = invalidation (files changed / rejected / rebuilt)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    book_id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS book_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT NOT NULL, from_state TEXT,
    to_state TEXT NOT NULL, at TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_book_states_book ON book_states(book_id);
"""


class IllegalTransition(Exception):
    pass


@dataclass(frozen=True)
class StateEvent:
    from_state: str | None
    to_state: str
    at: str
    actor: str
    note: str


class StateStore:
    def __init__(self, db_path: str | Path) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(db_path)
        self._c.executescript(_SCHEMA)

    def __enter__(self) -> StateStore:
        return self

    def __exit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._c.close()

    def current(self, book_id: str) -> str | None:
        row = self._c.execute("SELECT state FROM books WHERE book_id=?", (book_id,)).fetchone()
        return None if row is None else str(row[0])

    def ensure(self, book_id: str, actor: str = "forge") -> str:
        cur = self.current(book_id)
        if cur is None:
            self._write(book_id, None, "DRAFT", actor, "created")
            return "DRAFT"
        return cur

    def transition(self, book_id: str, to: str, actor: str = "forge", note: str = "") -> None:
        cur = self.ensure(book_id, actor)
        if to not in TRANSITIONS.get(cur, set()):
            raise IllegalTransition(f"{book_id}: {cur} -> {to} is not allowed")
        if to == "REJECTED" and not note.strip():
            raise IllegalTransition("a rejection needs a comment")
        self._write(book_id, cur, to, actor, note)

    def _write(self, book_id: str, frm: str | None, to: str, actor: str, note: str) -> None:
        at = datetime.now(UTC).isoformat(timespec="seconds")
        self._c.execute(
            "INSERT INTO books(book_id, state, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(book_id) DO UPDATE SET state=excluded.state, "
            "updated_at=excluded.updated_at",
            (book_id, to, at),
        )
        self._c.execute(
            "INSERT INTO book_states(book_id, from_state, to_state, at, actor, note) "
            "VALUES (?,?,?,?,?,?)",
            (book_id, frm, to, at, actor, note),
        )
        self._c.commit()

    def history(self, book_id: str) -> list[StateEvent]:
        rows = self._c.execute(
            "SELECT from_state, to_state, at, actor, note FROM book_states "
            "WHERE book_id=? ORDER BY id",
            (book_id,),
        ).fetchall()
        return [StateEvent(*r) for r in rows]
