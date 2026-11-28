"""Book spec (YAML) for classic books — see docs/SPEC.md §2."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from forge.core.models import LEVELS, Audience, Level

Trim = Literal["8.5x11", "8x10", "6x9", "8.5x8.5"]
FrontMatter = Literal["title", "copyright", "how_to_play", "table_of_contents"]
BackMatter = Literal["solutions", "about", "thank_you", "case_vault"]


def _default_distribution() -> dict[Level, float]:
    return {"easy": 30.0, "medium": 40.0, "hard": 30.0}


def _default_front() -> list[FrontMatter]:
    return ["title", "copyright", "how_to_play", "table_of_contents"]


def _default_back() -> list[BackMatter]:
    return ["solutions", "about", "thank_you"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BookInfo(_Model):
    title: str
    subtitle: str = ""
    author: str = "Anonymous"
    audience: Audience
    trim: Trim = "8.5x11"
    large_print: bool = False
    interior: Literal["bw", "color"] = "bw"
    content_pages: int = Field(default=100, ge=1, le=800)
    seed: int = Field(ge=0)


class TypeEntry(_Model):
    type: str
    weight: float = Field(default=1.0, gt=0)
    options: dict[str, Any] = Field(default_factory=dict)


class PuzzlesSection(_Model):
    mode: Literal["progressive", "mixed", "by_section"] = "progressive"
    distribution: dict[Level, float] = Field(default_factory=_default_distribution)
    types: list[TypeEntry] = Field(min_length=1)
    themes: Literal["auto"] | list[str] = "auto"
    theme: str | None = None

    @field_validator("distribution")
    @classmethod
    def _positive(cls, v: dict[Level, float]) -> dict[Level, float]:
        if not v or any(w < 0 for w in v.values()) or sum(v.values()) <= 0:
            raise ValueError("distribution needs at least one positive weight")
        return v

    def level_counts(self, total: int) -> dict[Level, int]:
        """Split `total` puzzles across levels (largest remainder, ordered easy → hard)."""
        levels = [lvl for lvl in LEVELS if self.distribution.get(lvl, 0) > 0]
        weight_sum = sum(self.distribution[lvl] for lvl in levels)
        exact = {lvl: total * self.distribution[lvl] / weight_sum for lvl in levels}
        counts = {lvl: int(exact[lvl]) for lvl in levels}
        leftover = total - sum(counts.values())
        by_remainder = sorted(
            levels, key=lambda lvl: (-(exact[lvl] - counts[lvl]), LEVELS.index(lvl))
        )
        for lvl in by_remainder[:leftover]:
            counts[lvl] += 1
        return counts


class SolutionsSection(_Model):
    per_page: int = Field(default=6, ge=1, le=20)


class BookSpec(_Model):
    book: BookInfo
    puzzles: PuzzlesSection
    front_matter: list[FrontMatter] = Field(default_factory=_default_front)
    back_matter: list[BackMatter] = Field(default_factory=_default_back)
    solutions: SolutionsSection = Field(default_factory=SolutionsSection)


def load_book_spec(path: str | Path) -> BookSpec:
    """Load and validate a book YAML file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"book spec not found: {p}")
    with p.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return BookSpec.model_validate(raw)
