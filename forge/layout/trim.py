"""Trim sizes and KDP margin rules (table lives in configs/kdp.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from forge.config import REPO_ROOT

KDP_RULES_PATH = REPO_ROOT / "configs" / "kdp.yaml"


class _Gutter(BaseModel):
    max_pages: int
    inside_in: float


class _Comfort(BaseModel):
    outside_in: float
    top_in: float
    bottom_in: float
    gutter_extra_in: float


class _Trim(BaseModel):
    width_in: float
    height_in: float


class KdpRules(BaseModel):
    checked_on: str
    min_pages: int
    max_pages: int
    outside_min_in: float
    gutter: list[_Gutter]
    comfort: _Comfort
    trims: dict[str, _Trim]


@lru_cache(maxsize=4)
def load_kdp_rules(path: Path = KDP_RULES_PATH) -> KdpRules:
    with path.open(encoding="utf-8") as fh:
        return KdpRules.model_validate(yaml.safe_load(fh))


@dataclass(frozen=True)
class TrimSize:
    name: str
    width_in: float
    height_in: float


@dataclass(frozen=True)
class Margins:
    inside: float
    outside: float
    top: float
    bottom: float


TRIMS: dict[str, TrimSize] = {
    name: TrimSize(name, t.width_in, t.height_in) for name, t in load_kdp_rules().trims.items()
}


def gutter_for(page_count: int) -> float:
    """KDP minimum inside margin for a given page count."""
    rules = load_kdp_rules()
    for row in rules.gutter:
        if page_count <= row.max_pages:
            return row.inside_in
    raise ValueError(f"page count {page_count} exceeds KDP maximum {rules.max_pages}")


def margins_for(page_count: int) -> Margins:
    """Comfortable margins that satisfy KDP minimums for `page_count` pages."""
    rules = load_kdp_rules()
    c = rules.comfort
    return Margins(
        inside=gutter_for(page_count) + c.gutter_extra_in,
        outside=max(c.outside_in, rules.outside_min_in),
        top=max(c.top_in, rules.outside_min_in),
        bottom=max(c.bottom_in, rules.outside_min_in),
    )


def pad_page_count(n: int, min_pages: int | None = None) -> int:
    """Smallest even page count ≥ max(n, min_pages). Defaults to KDP's minimum."""
    floor = load_kdp_rules().min_pages if min_pages is None else min_pages
    target = max(n, floor)
    return target + (target % 2)
