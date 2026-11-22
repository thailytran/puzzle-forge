"""output/<book_id>/vault.yaml: the final answer(s) and the shop listings of a book."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

VAULT_FILE = "vault.yaml"

TEMPLATE = """# Case Vault registration for this book (docs/CASEVAULT.md).
# Plaintext answers stay on this machine; only HMAC hashes are sent to the website.
answer_type: culprit_name        # culprit_name | unlock_code | both
culprit_name: []                 # accepted variants, e.g. ["Captain Reed", "Reed", "Elias Reed"]
unlock_code: []                  # e.g. ["4729"] (numeric codes must match exactly)
etsy_listing_ids: []             # Etsy listing ids selling this book
shopify_product_ids: []          # e.g. ["gid://shopify/Product/123"]
# CaseVault website (casevault.colorilax.com), spec 2026-11-21 section 5 - all optional:
book_code_prefix: ""             # e.g. CASE01 (Book Codes look like CASE01-7KQ2M9TX)
line: mystery                    # mystery | escape | adventure | hidden
series_id: ""                    # e.g. tamsin-hale
series_title: ""
series_order: 0                  # 1..12
series_total: 0                  # 8..12
next_book_id: ""                 # next book of the series (15% coupon target)
next_series_id: ""               # series whose Book 1 is the gift for finishing this series
release_date: ""                 # YYYY-MM-DD
skus: []                         # Etsy / Shopify SKUs (Etsy CSV matching)
etsy_url: ""
shop_url: ""
blurb: ""                        # spoiler-free description
extended_ending: ""              # shown on the website after a correct answer (not in the book)
"""


class VaultSpec(BaseModel):
    answer_type: Literal["culprit_name", "unlock_code", "both"]
    culprit_name: list[str] = Field(default_factory=list)
    unlock_code: list[str] = Field(default_factory=list)
    etsy_listing_ids: list[str | int] = Field(default_factory=list)
    shopify_product_ids: list[str] = Field(default_factory=list)
    book_code_prefix: str = ""
    line: Literal["mystery", "escape", "adventure", "hidden"] = "mystery"
    series_id: str = ""
    series_title: str = ""
    series_order: int = 0
    series_total: int = 0
    next_book_id: str = ""
    next_series_id: str = ""
    release_date: str = ""
    skus: list[str] = Field(default_factory=list)
    etsy_url: str = ""
    shop_url: str = ""
    blurb: str = ""
    extended_ending: str = ""

    @model_validator(mode="after")
    def _answers_present(self) -> VaultSpec:
        kinds = (
            ["culprit_name", "unlock_code"] if self.answer_type == "both" else [self.answer_type]
        )
        for k in kinds:
            if not [v for v in getattr(self, k) if str(v).strip()]:
                raise ValueError(f"vault.yaml: {k} needs at least one accepted answer")
        return self

    def kinds(self) -> list[str]:
        return ["culprit_name", "unlock_code"] if self.answer_type == "both" else [self.answer_type]


def load_vault_spec(out_dir: Path) -> VaultSpec | None:
    p = out_dir / VAULT_FILE
    if not p.is_file():
        return None
    return VaultSpec.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def init_vault_spec(out_dir: Path) -> Path:
    p = out_dir / VAULT_FILE
    if not p.exists():
        p.write_text(TEMPLATE, encoding="utf-8")
    return p
