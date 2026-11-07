"""Assign a SKU to a QA_PASSED book (state QA_PASSED -> SKU_ASSIGNED)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from forge.config import REPO_ROOT
from forge.ports import SkuError, SkuPort, SkuRequest

SKU_CONFIG = REPO_ROOT / "configs" / "sku.yaml"
SKU_FILE = "sku.json"
SKU_RE = re.compile(r"^(DEV-)?[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+-\d{4}-(SGL|SER\d{3}-\d{2})$")


@dataclass(frozen=True)
class SkuConfig:
    brand: str
    line: str
    format: str
    audience_codes: dict[str, str]
    aliases: dict[str, str]

    @classmethod
    def load(cls, path: Path = SKU_CONFIG) -> SkuConfig:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            raw["brand"],
            raw["line"],
            raw["format"],
            dict(raw["audience_codes"]),
            dict(raw.get("aliases", {})),
        )

    def code_for(self, audience: str) -> str:
        if audience not in self.audience_codes:
            raise SkuError(f"no Portal age code for audience {audience!r} in configs/sku.yaml")
        return self.audience_codes[audience]


def provider_from_env(db_path: Path) -> SkuPort:
    from forge.config import get_settings

    st = get_settings()
    kind = st.sku_provider
    if kind == "dev" and st.is_prod:
        raise SkuError("FORGE_ENV=prod refuses the dev SKU provider (DEV- SKUs are for tests only)")
    if kind == "dev":
        from forge.adapters.sku_dev import DevSkuProvider

        return DevSkuProvider(db_path)
    if kind == "hub":
        from forge.adapters.sku_hub import HubSkuProvider

        return HubSkuProvider(os.environ.get("HUB_URL", ""), st.secret("HUB_TOKEN"))
    raise SkuError(f"FORGE_SKU_PROVIDER must be hub or dev, got {kind!r}")


def request_for(manifest: dict[str, Any], cfg: SkuConfig) -> SkuRequest:
    book = manifest["spec"]["book"]
    return SkuRequest(
        book_id=manifest["book_id"],
        title=book["title"],
        audience_code=cfg.code_for(book["audience"]),
        brand=cfg.brand,
        line=cfg.line,
        format=cfg.format,
    )


def existing_sku(out_dir: Path) -> dict[str, Any] | None:
    p = out_dir / SKU_FILE
    return dict(json.loads(p.read_text(encoding="utf-8"))) if p.is_file() else None


def assign_sku(out_dir: Path, provider: SkuPort, cfg: SkuConfig | None = None) -> dict[str, Any]:
    """Idempotent: a book keeps its SKU (stored in sku.json, outside the QA hash lock)."""
    found = existing_sku(out_dir)
    if found:
        return found
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    res = provider.assign(request_for(manifest, cfg or SkuConfig.load()))
    if not SKU_RE.match(res.sku):
        raise SkuError(f"SKU {res.sku!r} does not match the Portal format")
    data = {"sku": res.sku, "provider": res.provider, "book_id": manifest["book_id"]}
    (out_dir / SKU_FILE).write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data
