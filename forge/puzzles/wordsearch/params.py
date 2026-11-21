"""Word search parameters by level and audience (SPEC §3)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from forge.core.models import Audience, Level

DIRS: dict[str, tuple[int, int]] = {
    "E": (0, 1),
    "S": (1, 0),
    "SE": (1, 1),
    "NE": (-1, 1),
    "W": (0, -1),
    "N": (-1, 0),
    "NW": (-1, -1),
    "SW": (1, -1),
}
BACKWARD = frozenset({"W", "N", "NW", "SW"})
DIAGONAL = frozenset({"SE", "NE", "NW", "SW"})
FORWARD_DIRS = ("E", "S", "SE", "NE")
ALL_DIRS = tuple(DIRS)


@dataclass(frozen=True)
class WsParams:
    rows: int
    cols: int
    min_words: int
    max_words: int
    dirs: tuple[str, ...]
    decoys: int
    overlap_bias: float  # probability of choosing a max-overlap placement
    word_letter_fill: float  # 0 = uniform filler letters, 1 = filler drawn from word letters
    shape: str = "rect"


_BY_LEVEL: dict[Level, WsParams] = {
    "very_easy": WsParams(10, 10, 6, 8, ("E", "S"), 0, 0.0, 0.0),
    "easy": WsParams(12, 12, 8, 12, ("E", "S"), 0, 0.1, 0.0),
    "medium": WsParams(14, 14, 15, 20, ("E", "S", "SE", "NE"), 1, 0.3, 0.3),
    "hard": WsParams(18, 18, 25, 30, ALL_DIRS, 4, 0.6, 0.6),
    "expert": WsParams(20, 20, 30, 35, ALL_DIRS, 8, 0.8, 0.8),
}


def resolve_params(
    level: Level,
    audience: Audience,
    size: tuple[int, int] | None = None,
    options: dict[str, Any] | None = None,
) -> WsParams:
    opts = options or {}
    p = _BY_LEVEL[level]
    if audience == "kids_6_8":
        # SPEC: no backwards words, big cells → at most 12x12, E/S (+SE from medium)
        dirs: tuple[str, ...] = ("E", "S") if level in ("very_easy", "easy") else ("E", "S", "SE")
        p = replace(
            p,
            rows=min(p.rows, 12),
            cols=min(p.cols, 12),
            max_words=min(p.max_words, 14),
            min_words=min(p.min_words, 10),
            dirs=dirs,
            decoys=0,
        )
    elif audience == "kids_9_12":
        dirs = tuple(d for d in p.dirs if d not in BACKWARD) if level != "expert" else p.dirs
        p = replace(
            p,
            rows=min(p.rows, 15),
            cols=min(p.cols, 15),
            dirs=dirs,
            max_words=min(p.max_words, 22),
            min_words=min(p.min_words, 18),
        )
    elif audience == "senior_large_print":
        p = replace(
            p,
            rows=min(p.rows, 15),
            cols=min(p.cols, 15),
            max_words=min(p.max_words, 22),
            min_words=min(p.min_words, 18),
        )
    if size is not None:
        p = replace(p, rows=size[0], cols=size[1])
    dirs_opt = opts.get("directions")
    if isinstance(dirs_opt, list):
        unknown = [d for d in dirs_opt if d not in DIRS]
        if unknown:
            raise ValueError(f"unknown directions {unknown}; use {list(DIRS)}")
        p = replace(p, dirs=tuple(dirs_opt))
    if "words" in opts:
        n = int(opts["words"])
        p = replace(p, min_words=n, max_words=n)
    if "decoys" in opts:
        p = replace(p, decoys=int(opts["decoys"]))
    if "shape" in opts:
        p = replace(p, shape=str(opts["shape"]))
    return p
