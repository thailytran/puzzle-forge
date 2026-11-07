"""Pure planning: which puzzle (type, level, theme) goes on which content page."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge.core.book import BookSpec
from forge.core.models import LEVELS, Level
from forge.core.seeds import derive_seed, make_rng
from forge.wordlists import available_themes

THEMED_TYPES = frozenset({"wordsearch", "scramble", "crossword"})
# Highest level a type can honestly reach (measured difficulty) and per-audience ceilings
# (SPEC §3: kids 6-8 use the very_easy/easy bands). Requests above are capped and recorded.
TYPE_MAX_LEVEL: dict[str, Level] = {"scramble": "hard", "cryptogram": "hard"}
AUDIENCE_MAX_LEVEL: dict[str, Level] = {"kids_6_8": "easy"}


def cap_level(level: Level, type_: str, audience: str) -> Level:
    caps = [c for c in (TYPE_MAX_LEVEL.get(type_), AUDIENCE_MAX_LEVEL.get(audience)) if c]
    for c in caps:
        if LEVELS.index(level) > LEVELS.index(c):
            level = c
    return level


SECTION = 10


@dataclass(frozen=True)
class Slot:
    index: int  # 0-based puzzle number in the book
    type: str
    level: Level
    theme: str | None
    options: dict[str, Any] = field(default_factory=dict)
    requested_level: Level | None = None  # set when the level was capped


def _type_sequence(spec: BookSpec, n: int) -> list[int]:
    """Smooth weighted round-robin over type entries (deterministic)."""
    weights = [t.weight for t in spec.puzzles.types]
    total = sum(weights)
    credit = [0.0] * len(weights)
    out: list[int] = []
    for _ in range(n):
        for i, w in enumerate(weights):
            credit[i] += w
        best = max(range(len(weights)), key=lambda i: (credit[i], -i))
        credit[best] -= total
        out.append(best)
    return out


def _levels(spec: BookSpec, n: int) -> list[Level]:
    mode = spec.puzzles.mode
    if mode == "mixed":
        # each section of 10 carries the whole level mix, easy → hard inside the section
        out: list[Level] = []
        for k in range(0, n, SECTION):
            size = min(SECTION, n - k)
            sc = spec.puzzles.level_counts(size)
            out += [lvl for lvl in LEVELS for _ in range(sc.get(lvl, 0))]
        return out
    counts = spec.puzzles.level_counts(n)
    return [lvl for lvl in LEVELS for _ in range(counts.get(lvl, 0))]  # easy → hard


def _themes(spec: BookSpec) -> list[str]:
    if isinstance(spec.puzzles.themes, list) and spec.puzzles.themes:
        return list(spec.puzzles.themes)
    pool = [t for t in available_themes() if t != "short_words"]
    if spec.puzzles.theme and spec.puzzles.theme in pool:
        pool.remove(spec.puzzles.theme)
        pool.insert(0, spec.puzzles.theme)  # book theme first, then variety
    rng = make_rng(derive_seed(spec.book.seed, "themes"))
    rest = pool[1:]
    rng.shuffle(rest)
    return pool[:1] + rest


def plan_book(spec: BookSpec) -> list[Slot]:
    n = spec.book.content_pages
    entries = spec.puzzles.types
    levels = _levels(spec, n)
    if spec.puzzles.mode == "by_section":
        seq = sorted(_type_sequence(spec, n))  # type 0 block, then type 1 block, ...
        per_type: dict[int, list[int]] = {}
        for pos, t in enumerate(seq):
            per_type.setdefault(t, []).append(pos)
        levels_by_pos: list[Level] = [levels[0]] * n
        for positions in per_type.values():
            sub = _levels(spec, len(positions))
            for p, lvl in zip(positions, sub, strict=True):
                levels_by_pos[p] = lvl
        levels = levels_by_pos
    else:
        seq = _type_sequence(spec, n)
    themes = _themes(spec)
    theme_i = 0
    slots: list[Slot] = []
    for i in range(n):
        entry = entries[seq[i]]
        theme = None
        if entry.type in THEMED_TYPES:
            theme = themes[theme_i % len(themes)]
            theme_i += 1
        opts = {
            k: v
            for k, v in entry.options.items()
            if not (k == "directions" and v == "auto_by_level")
        }
        level = cap_level(levels[i], entry.type, spec.book.audience)
        requested = levels[i] if level != levels[i] else None
        slots.append(Slot(i, entry.type, level, theme, opts, requested))
    return slots
