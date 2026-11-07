"""Content plan: per-page sub-theme, vocabulary, quotes and illustration description.

Written by the AI planner (PC.4) or by hand; validated here; read by the builder. The plan is the
single source of a book's words, so it is where diversity / age-fit / dictionary rules are enforced.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from forge.book.plan import Slot
from forge.config import REPO_ROOT
from forge.core.models import Level
from forge.wordlists import blocklist, normalize_word
from forge.wordlists.dictionary import common_words, words

PLAN_FILE = "content_plan.yaml"
ILLUSTRATIONS_FILE = "illustration_requests.json"
RULES_PATH = REPO_ROOT / "configs" / "content_rules.yaml"
WORD_TYPES = ("wordsearch", "scramble", "crossword")
KIDS = ("kids_6_8", "kids_9_12")


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    source: str = "Original"


class PagePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int = Field(ge=1)
    type: str
    level: Level
    subtheme: str
    words: list[str] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    illustration: str = ""


class ContentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    book_theme: str
    audience: str
    glossary: list[str] = Field(default_factory=list)  # topic terms confirmed by AI + dictionary
    pages: list[PagePlan]

    def page(self, n: int) -> PagePlan | None:
        return next((p for p in self.pages if p.n == n), None)


@lru_cache(maxsize=1)
def content_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    return dict(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_plan(path: Path) -> ContentPlan:
    return ContentPlan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def save_plan(plan: ContentPlan, path: Path) -> None:
    path.write_text(
        yaml.safe_dump(plan.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def ws_rule(audience: str, level: str) -> dict[str, Any] | None:
    ws = content_rules()["wordsearch"]
    if audience == "senior_large_print":
        return dict(ws["large_print"])
    group = {"kids_6_8": "kids", "kids_9_12": "kids_9_12"}.get(audience, "adult")
    rule = ws.get(group, {}).get(level) or (ws["kids"].get(level) if group == "kids_9_12" else None)
    return dict(rule) if rule else None


def min_words(page_type: str, audience: str, level: str) -> int:
    if page_type == "wordsearch":
        r = ws_rule(audience, level)
        return int(r["words"][0]) if r else 0
    if page_type == "scramble":
        return int(content_rules()["scramble"]["words_per_page"])
    return 0


def validate_plan(plan: ContentPlan, slots: list[Slot], audience: str) -> list[str]:
    """Problems (empty = OK). Checks structure against the book plan and the content rules."""
    rules = content_rules()
    out: list[str] = []
    if len(plan.pages) != len(slots):
        out.append(f"plan has {len(plan.pages)} pages, book needs {len(slots)}")
    subthemes = Counter(p.subtheme.strip().lower() for p in plan.pages)
    out += [f"sub-theme used on {k} pages: {s!r}" for s, k in subthemes.items() if k > 1]
    known = set(words()) | set(common_words()) | {normalize_word(g) for g in plan.glossary}
    kids_common = set(common_words())
    kids_max = int(rules["age_fit"]["kids_max_word_len"])
    uses: Counter[str] = Counter()
    for slot, page in zip(slots, plan.pages, strict=False):
        tag = f"page {page.n}"
        if (page.type, page.level) != (slot.type, slot.level):
            out.append(
                f"{tag}: plan says {page.type}/{page.level}, book plan {slot.type}/{slot.level}"
            )
        ws = [normalize_word(w) for w in page.words]
        uses.update(set(ws))
        need = min_words(page.type, audience, page.level)
        if page.type in WORD_TYPES and len(set(ws)) < need:
            out.append(f"{tag}: {len(set(ws))} words, needs ≥ {need}")
        for w in ws:
            if w not in known:
                out.append(f"{tag}: {w} not in dictionary or glossary")
            if audience in KIDS and (w in blocklist() or len(w) > kids_max or w not in kids_common):
                out.append(f"{tag}: {w} not a common kids' word (≤ {kids_max} letters)")
        if page.type == "cryptogram" and not page.quotes:
            out.append(f"{tag}: cryptogram page without quotes")
        if not page.illustration.strip():
            out.append(f"{tag}: missing illustration description")
    limit = int(rules["diversity"]["max_word_repeats_per_book"])
    out += [f"{w} used on {k} pages (max {limit})" for w, k in uses.items() if k > limit]
    return out


def illustration_requests(plan: ContentPlan) -> list[dict[str, Any]]:
    return [
        {
            "page": p.n,
            "subtheme": p.subtheme,
            "description": p.illustration,
            "words": [normalize_word(w) for w in p.words][:12],
        }
        for p in plan.pages
        if p.illustration.strip()
    ]
