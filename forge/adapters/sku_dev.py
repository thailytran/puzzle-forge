"""DevSkuProvider: TESTS / LOCAL DEMOS ONLY. Every SKU starts with "DEV-" so it can never collide
with a real Portal SKU. Counter per prefix in a local SQLite file."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from forge.ports import SkuRequest, SkuResult

DEV_PREFIX = "DEV-"


class DevSkuProvider:
    name = "dev"

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS dev_sku_counters (prefix TEXT PRIMARY KEY, last INT)"
            )

    def assign(self, req: SkuRequest) -> SkuResult:
        prefix = f"{DEV_PREFIX}{req.brand}-{req.audience_code}-{req.line}-{req.format}"
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO dev_sku_counters(prefix,last) VALUES (?,1) "
                "ON CONFLICT(prefix) DO UPDATE SET last=last+1",
                (prefix,),
            )
            (n,) = c.execute(
                "SELECT last FROM dev_sku_counters WHERE prefix=?", (prefix,)
            ).fetchone()
        tail = f"{req.series_code}-{int(req.volume_no or 1):02d}" if req.series_code else "SGL"
        return SkuResult(sku=f"{prefix}-{int(n):04d}-{tail}", provider=self.name)
