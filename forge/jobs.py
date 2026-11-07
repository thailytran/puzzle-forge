"""Job queue (SQLite) + handlers run by `forge worker` (systemd forge-worker).

Kinds: build_book {spec_yaml} -> build + QA gate (auto-fix); qa_run {out_dir}; vault_sync {}."""

from __future__ import annotations

import io
import json
import sqlite3
import traceback
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forge.config import Settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', title TEXT NOT NULL DEFAULT '',
    book_id TEXT NOT NULL DEFAULT '', out_dir TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '', log TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""
KINDS = ("build_book", "qa_run", "vault_sync")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class Job:
    id: int
    kind: str
    payload: dict[str, Any]
    status: str
    title: str
    book_id: str
    out_dir: str
    result: str
    log: str
    created_at: str
    started_at: str | None
    finished_at: str | None


class JobQueue:
    def __init__(self, db_path: str | Path) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(db_path, timeout=30)
        self.c.executescript(_SCHEMA)

    def close(self) -> None:
        self.c.close()

    def add(self, kind: str, payload: dict[str, Any], title: str = "") -> int:
        if kind not in KINDS:
            raise ValueError(f"unknown job kind {kind!r}")
        with self.c:
            cur = self.c.execute(
                "INSERT INTO jobs(kind, payload, title, created_at) VALUES (?,?,?,?)",
                (kind, json.dumps(payload), title, _now()),
            )
        return int(cur.lastrowid or 0)

    def _row(self, r: tuple[Any, ...]) -> Job:
        return Job(r[0], r[1], json.loads(r[2]), *r[3:])

    _COLS = (
        "id, kind, payload, status, title, book_id, out_dir, result, log, created_at, "
        "started_at, finished_at"
    )

    def get(self, job_id: int) -> Job | None:
        r = self.c.execute(f"SELECT {self._COLS} FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row(r) if r else None

    def recent(self, limit: int = 50) -> list[Job]:
        rows = self.c.execute(
            f"SELECT {self._COLS} FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row(r) for r in rows]

    def counts(self) -> dict[str, int]:
        return dict(self.c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())

    def claim(self) -> Job | None:
        """Atomically take the oldest queued job."""
        with self.c:
            r = self.c.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE id = "
                "(SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1) RETURNING id",
                (_now(),),
            ).fetchone()
        return self.get(int(r[0])) if r else None

    def finish(self, job_id: int, ok: bool, result: dict[str, Any], log: str) -> None:
        with self.c:
            self.c.execute(
                "UPDATE jobs SET status=?, result=?, log=?, finished_at=?, book_id=?, out_dir=? "
                "WHERE id=?",
                (
                    "done" if ok else "failed",
                    json.dumps(result),
                    log[-20000:],
                    _now(),
                    str(result.get("book_id", "")),
                    str(result.get("out_dir", "")),
                    job_id,
                ),
            )

    def requeue_stale(self) -> int:
        """Jobs left 'running' by a crash/restart go back to the queue (worker start-up)."""
        with self.c:
            return self.c.execute(
                "UPDATE jobs SET status='queued', started_at=NULL WHERE status='running'"
            ).rowcount


# --------------------------------------------------------------------------- handlers
def _build_book(st: Settings, p: dict[str, Any]) -> dict[str, Any]:
    import yaml

    from forge.book.builder import build_book
    from forge.core.book import BookSpec
    from forge.qa.fixer import regenerate_failing
    from forge.qa.gate import run_gate

    spec = BookSpec.model_validate(yaml.safe_load(p["spec_yaml"]))
    out = build_book(spec, st.output_dir, st.db_path)
    report = run_gate(out, st.db_path, fixer=regenerate_failing)
    return {"book_id": report.book_id, "out_dir": str(out), "qa": report.result}


def _qa_run(st: Settings, p: dict[str, Any]) -> dict[str, Any]:
    from forge.qa.fixer import regenerate_failing
    from forge.qa.gate import run_gate

    out = Path(p["out_dir"])
    report = run_gate(out, st.db_path, fixer=regenerate_failing)
    return {"book_id": report.book_id, "out_dir": str(out), "qa": report.result}


def _vault_sync(st: Settings, p: dict[str, Any]) -> dict[str, Any]:
    from forge.vault.sync import VaultOutbox, sender_for

    box = VaultOutbox(st.db_path)
    try:
        return box.sync(sender_for(st.vault_url, st.vault_token, st.data_dir), force=True)
    finally:
        box.close()


HANDLERS: dict[str, Callable[[Settings, dict[str, Any]], dict[str, Any]]] = {
    "build_book": _build_book,
    "qa_run": _qa_run,
    "vault_sync": _vault_sync,
}


def run_one(q: JobQueue, st: Settings, notify: Callable[[str], None] | None = None) -> Job | None:
    job = q.claim()
    if job is None:
        return None
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            result = HANDLERS[job.kind](st, job.payload)
        ok = result.get("qa", "PASSED") == "PASSED" and not result.get("failed")
        q.finish(job.id, True, result, buf.getvalue())
        if notify:
            notify(
                f"Job #{job.id} {job.kind} {job.title}: {result.get('qa', 'done')}"
                + ("" if ok else " (check the QA report)")
            )
    except Exception as exc:  # a failing job must never stop the worker
        q.finish(job.id, False, {"error": str(exc)[:500]}, buf.getvalue() + traceback.format_exc())
        if notify:
            notify(f"Job #{job.id} {job.kind} {job.title} FAILED: {str(exc)[:200]}")
    return q.get(job.id)
