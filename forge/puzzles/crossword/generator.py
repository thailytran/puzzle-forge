"""Criss-cross crossword builder: interlock theme words on a grid (no GPL code)."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from forge.core.models import Level, PuzzleSpec
from forge.puzzles.crossword.grid import BLOCK, Rows
from forge.wordlists import blocklist, normalize_word, theme_words


@dataclass(frozen=True)
class CwParams:
    words: int
    max_size: int


_BY_LEVEL: dict[Level, CwParams] = {
    "very_easy": CwParams(6, 9),
    "easy": CwParams(9, 11),
    "medium": CwParams(12, 13),
    "hard": CwParams(16, 15),
    "expert": CwParams(20, 17),
}


def resolve_params(spec: PuzzleSpec) -> CwParams:
    p = _BY_LEVEL[spec.level]
    if spec.audience == "kids_6_8":
        p = replace(p, words=min(p.words, 9), max_size=min(p.max_size, 11))
    if "words" in spec.options:
        p = replace(p, words=int(spec.options["words"]))
    return p


def word_pool(spec: PuzzleSpec, max_len: int) -> list[str]:
    raw = spec.words if spec.words else list(theme_words(spec.theme or "animals"))
    out = [normalize_word(w) for w in raw]
    return list(dict.fromkeys(w for w in out if 3 <= len(w) <= max_len and w not in blocklist()))


Cells = dict[tuple[int, int], str]


def _fits(cells: Cells, w: str, r: int, c: int, d: str) -> int:
    """-1 if illegal, else number of crossings."""
    dr, dc = (0, 1) if d == "A" else (1, 0)
    if cells.get((r - dr, c - dc)) or cells.get((r + dr * len(w), c + dc * len(w))):
        return -1
    crossings = 0
    for i, ch in enumerate(w):
        cell = (r + dr * i, c + dc * i)
        cur = cells.get(cell)
        if cur is not None:
            if cur != ch:
                return -1
            crossings += 1
            continue
        # new letter: no side neighbours (would create unintended words)
        side = [(cell[0] + dc, cell[1] + dr), (cell[0] - dc, cell[1] - dr)]
        if any(s in cells for s in side):
            return -1
    return crossings


def _bbox(cells: Cells) -> tuple[int, int, int, int]:
    rs = [r for r, _ in cells]
    cs = [c for _, c in cells]
    return min(rs), min(cs), max(rs), max(cs)


def build(spec: PuzzleSpec, rng: random.Random) -> tuple[Rows, list[str]] | None:
    p = resolve_params(spec)
    pool = word_pool(spec, p.max_size)
    rng.shuffle(pool)
    pool.sort(key=len, reverse=True)
    if len(pool) < 4:
        return None
    first = pool[0]
    cells: Cells = {(0, i): ch for i, ch in enumerate(first)}
    placed = [first]
    for w in pool[1:] + pool[1:]:  # second pass: earlier misfits may fit now
        if len(placed) >= p.words:
            break
        if w in placed:
            continue
        r0, c0, r1, c1 = _bbox(cells)
        best: list[tuple[int, int, str]] = []
        best_score = 0
        for (cr, cc), ch in list(cells.items()):
            for i, wch in enumerate(w):
                if wch != ch:
                    continue
                for d in ("A", "D"):
                    r, c = (cr, cc - i) if d == "A" else (cr - i, cc)
                    x = _fits(cells, w, r, c, d)
                    if x <= 0:
                        continue
                    rr1 = max(r1, r + (0 if d == "A" else len(w) - 1))
                    cc1 = max(c1, c + (len(w) - 1 if d == "A" else 0))
                    if max(rr1 - min(r0, r), cc1 - min(c0, c)) + 1 > p.max_size:
                        continue
                    if x > best_score:
                        best, best_score = [(r, c, d)], x
                    elif x == best_score:
                        best.append((r, c, d))
        if not best:
            continue
        r, c, d = best[rng.randrange(len(best))]
        dr, dc = (0, 1) if d == "A" else (1, 0)
        for i, ch in enumerate(w):
            cells[(r + dr * i, c + dc * i)] = ch
        placed.append(w)
    if len(placed) < min(max(4, -(-p.words * 3 // 4)), len(pool)):
        return None
    r0, c0, r1, c1 = _bbox(cells)
    rows = ["".join(cells.get((r, c), BLOCK) for c in range(c0, c1 + 1)) for r in range(r0, r1 + 1)]
    return rows, placed
