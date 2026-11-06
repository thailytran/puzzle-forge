"""Deterministic sudoku generator: seeded full grid → clue removal guided by the target level."""

from __future__ import annotations

import random
from dataclasses import dataclass

import rustoku

from forge.core.models import Audience, Level, PuzzleSpec, ShadedCells
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.sudoku.grading import grade, keeps_level, very_easy_givens
from forge.puzzles.sudoku.grid import Grid, copy, count_solutions, random_full_grid, to_string


@dataclass(frozen=True)
class SdParams:
    size: int
    target: Level
    min_givens: int  # stop removing at this many givens
    symmetric: bool


def default_size(level: Level, audience: Audience) -> int:
    if audience == "kids_6_8":
        return 4 if level in ("very_easy", "easy") else 6
    if audience == "kids_9_12":
        return 6 if level in ("very_easy", "easy") else 9
    return 9


def resolve_params(spec: PuzzleSpec, rng: random.Random) -> SdParams:
    size = int(spec.options.get("size", default_size(spec.level, spec.audience)))
    if size not in (4, 6, 9):
        raise ValueError("sudoku size must be 4, 6 or 9")
    cells = size * size
    if spec.level == "very_easy":
        floor = very_easy_givens(size) + rng.randint(0, max(1, cells // 20))
    elif spec.level == "easy":
        floor = round(cells * 0.42) + rng.randint(0, max(1, cells // 27))
    else:
        floor = 0  # minimal puzzle; level decided by the technique filter
    symmetric = size == 9 and bool(spec.options.get("symmetric", True))
    return SdParams(size, spec.level, floor, symmetric)


def _unique(grid: Grid) -> bool:
    if len(grid) == 9:
        return int(rustoku.count_solutions(to_string(grid), 2)) == 1
    return count_solutions(grid, 2) == 1


def _shaded(spec: PuzzleSpec, n: int) -> dict[tuple[int, int], int]:
    sc = find_constraint(spec, ShadedCells)
    if sc is None:
        return {}
    digits = [ch for ch in sc.expect if ch.isdigit()]
    if len(digits) != len(sc.cells):
        raise GenerationError("shaded_cells: expect must have one digit per cell")
    fixed: dict[tuple[int, int], int] = {}
    for (r, c), d in zip(sc.cells, digits, strict=True):
        v = int(d)
        if not (0 <= r < n and 0 <= c < n) or not (1 <= v <= n):
            raise GenerationError(f"shaded_cells: ({r},{c})={v} does not fit a {n}x{n} sudoku")
        if fixed.get((r, c), v) != v:
            raise GenerationError(f"shaded_cells: conflicting values for ({r},{c})")
        fixed[(r, c)] = v
    return fixed


def build(spec: PuzzleSpec, rng: random.Random) -> tuple[Grid, Grid, Level] | None:
    """One attempt → (givens, solution, graded level) or None."""
    p = resolve_params(spec, rng)
    n = p.size
    fixed = _shaded(spec, n)
    solution = random_full_grid(n, rng, fixed)
    if solution is None:
        raise GenerationError("shaded_cells: the requested digits cannot coexist in a sudoku")
    givens = copy(solution)

    def group(r: int, c: int) -> list[tuple[int, int]]:
        if p.symmetric and (n - 1 - r, n - 1 - c) != (r, c):
            return [(r, c), (n - 1 - r, n - 1 - c)]
        return [(r, c)]

    # shaded cells must be solved by the reader → remove them first
    for cell in fixed:
        for r, c in group(*cell):
            givens[r][c] = 0
    if not _unique(givens):
        return None

    order = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(order)
    count = sum(1 for row in givens for v in row if v)
    for r, c in order:
        if givens[r][c] == 0:
            continue
        cells = group(r, c)
        if count - len(cells) < p.min_givens:
            continue
        saved = [givens[rr][cc] for rr, cc in cells]
        for rr, cc in cells:
            givens[rr][cc] = 0
        if _unique(givens) and keeps_level(givens, p.target):
            count -= len(cells)
        else:
            for (rr, cc), v in zip(cells, saved, strict=True):
                givens[rr][cc] = v
    return givens, solution, grade(givens)
