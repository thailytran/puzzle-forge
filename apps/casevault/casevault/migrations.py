"""Schema versions. Tables are created by SQLAlchemy (create_all); later changes are appended
here as (version, [SQL]) and run once, in order, inside one transaction each."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, text

from casevault import db as T

MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, []),  # baseline (P9): tables from casevault/db.py
]


def migrate(engine: Engine) -> int:
    T.md.create_all(engine)
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE IF NOT EXISTS cv_schema (version INTEGER PRIMARY KEY, "
                "applied_at VARCHAR(40) NOT NULL)"
            )
        )
        done = {r[0] for r in c.execute(text("SELECT version FROM cv_schema"))}
    for version, statements in MIGRATIONS:
        if version in done:
            continue
        with engine.begin() as c:
            for sql in statements:
                c.execute(text(sql))
            c.execute(
                text("INSERT INTO cv_schema (version, applied_at) VALUES (:v, :t)"),
                {"v": version, "t": datetime.now(UTC).isoformat()},
            )
    with engine.connect() as c:
        return int(c.execute(text("SELECT COALESCE(MAX(version), 0) FROM cv_schema")).scalar_one())
