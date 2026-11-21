"""HubSkuProvider: SKU from the HALOSPARK Product Hub's shared counter.

Contract (halospark-suite tools/product-hub/app/main.py, checked 2026-11-07):
  POST {HUB_URL}/api/products      header X-Hub-Token: <HUB_TOKEN>
  body {topic, title, audience, line, format, brand, source, keyword_main, keywords, note, ...}
  → 200 JSON product row incl. "sku"  (401 on a bad token)
HUB_URL is the Hub hooks base, e.g. https://<portal>/hooks/product-hub
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from forge.ports import SkuError, SkuRequest, SkuResult

TIMEOUT_S = 20


class HubSkuProvider:
    name = "hub"

    def __init__(self, base_url: str, token: str) -> None:
        if not base_url or not token:
            raise SkuError("HUB_URL and HUB_TOKEN must be set in .env for the Hub SKU provider")
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "X-Hub-Token": self.token},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return dict(json.loads(resp.read().decode() or "{}"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise SkuError(f"Hub {path}: HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SkuError(f"Hub unreachable at {self.base_url}: {exc}") from exc

    def assign(self, req: SkuRequest) -> SkuResult:
        body: dict[str, Any] = {
            "topic": req.title,
            "title": req.title,
            "audience": req.audience_code,
            "line": req.line,
            "format": req.format,
            "brand": req.brand,
            "source": "puzzle-forge",
            "keyword_main": req.keyword_main or "",
            "keywords": req.keywords,
            "note": f"puzzle-forge book_id={req.book_id}",
            "external_id": req.book_id,  # proposed idempotency key (ignored by Hub 3.1.0)
        }
        if req.volume_no is not None:
            body["volume_no"] = req.volume_no
        row = self._post("/api/products", body)
        sku = row.get("sku")
        if not isinstance(sku, str) or not sku:
            raise SkuError(f"Hub answered without a SKU: {str(row)[:200]}")
        return SkuResult(sku=sku, provider=self.name, raw=row)
