"""Cost ledger + response cache + budgets (SQLite, same db as the registry)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, task TEXT NOT NULL,
    provider TEXT NOT NULL, model TEXT NOT NULL, book_id TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0, cached INTEGER NOT NULL DEFAULT 0,
    ok INTEGER NOT NULL DEFAULT 1, error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_at ON ai_usage(at);
CREATE TABLE IF NOT EXISTS ai_cache (
    key TEXT PRIMARY KEY, task TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
    response TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_alerts (period TEXT PRIMARY KEY, at TEXT NOT NULL);
"""


def now() -> datetime:
    return datetime.now(UTC)


class Ledger:
    def __init__(self, db_path: str | Path) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(db_path)
        self.c.executescript(_SCHEMA)

    def close(self) -> None:
        self.c.close()

    # usage --------------------------------------------------------------------------------
    def record(
        self,
        task: str,
        provider: str,
        model: str,
        book_id: str,
        tin: int,
        tout: int,
        cost: float,
        cached: bool = False,
        ok: bool = True,
        error: str = "",
    ) -> None:
        with self.c:
            self.c.execute(
                "INSERT INTO ai_usage(at, task, provider, model, book_id, input_tokens, "
                "output_tokens, cost_usd, cached, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now().isoformat(),
                    task,
                    provider,
                    model,
                    book_id,
                    tin,
                    tout,
                    cost,
                    int(cached),
                    int(ok),
                    error[:300],
                ),
            )

    def spent(self, since: datetime | None = None, book_id: str | None = None) -> float:
        q, args = "SELECT COALESCE(SUM(cost_usd), 0) FROM ai_usage WHERE 1=1", []
        if since is not None:
            q += " AND at >= ?"
            args.append(since.isoformat())
        if book_id:
            q += " AND book_id = ?"
            args.append(book_id)
        return float(self.c.execute(q, args).fetchone()[0])

    def periods(self) -> dict[str, datetime]:
        t = now()
        return {
            "day": t.replace(hour=0, minute=0, second=0, microsecond=0),
            "month": t.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        }

    def report(self, by: str = "task", days: int = 30) -> list[dict[str, Any]]:
        if by not in ("task", "provider", "model", "book_id", "day"):
            raise ValueError("by must be task | provider | model | book_id | day")
        col = "substr(at, 1, 10)" if by == "day" else by
        since = (now() - timedelta(days=days)).isoformat()
        rows = self.c.execute(
            f"SELECT {col}, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(cost_usd), "
            "SUM(cached), SUM(1 - ok) FROM ai_usage WHERE at >= ? GROUP BY 1 ORDER BY 5 DESC",
            (since,),
        ).fetchall()
        return [
            {
                by: r[0],
                "calls": r[1],
                "input_tokens": r[2] or 0,
                "output_tokens": r[3] or 0,
                "cost_usd": round(r[4] or 0.0, 4),
                "cached": r[5] or 0,
                "errors": r[6] or 0,
            }
            for r in rows
        ]

    def alert_once(self, period_key: str) -> bool:
        """True the first time a warning for this period is raised."""
        try:
            with self.c:
                self.c.execute(
                    "INSERT INTO ai_alerts(period, at) VALUES (?, ?)",
                    (period_key, now().isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    # cache ----------------------------------------------------------------------------------
    def cache_get(self, key: str, ttl_days: int) -> dict[str, Any] | None:
        row = self.c.execute(
            "SELECT response, created_at FROM ai_cache WHERE key=?", (key,)
        ).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row[1]) < now() - timedelta(days=ttl_days):
            return None
        return dict(json.loads(row[0]))

    def cache_put(
        self, key: str, task: str, provider: str, model: str, response: dict[str, Any]
    ) -> None:
        with self.c:
            self.c.execute(
                "INSERT OR REPLACE INTO ai_cache(key, task, provider, model, response, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (key, task, provider, model, json.dumps(response), now().isoformat()),
            )
