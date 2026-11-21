"""Technique-based sudoku grading.

9x9: rustoku's human-technique trace (MIT). `solve_steps(p, set)` marks guesses with technique
"None"; the puzzle's level is the smallest technique set that solves it without guessing.
4x4 / 6x6: our singles solver (rustoku is 9x9 only).
"""

from __future__ import annotations

from collections import Counter

import rustoku

from forge.core.models import LEVELS, Level
from forge.puzzles.sudoku.grid import Grid, logic_solve, to_string

RUSTOKU_SETS: tuple[str, ...] = ("medium", "hard", "expert")


def logical_at(grid: Grid, technique_set: str) -> bool:
    """True if rustoku solves the 9x9 grid using only `technique_set`, without guessing."""
    res = rustoku.solve_steps(to_string(grid), technique_set)
    if res is None:
        return False
    return not any(s["technique"] == "None" for s in res["steps"])


def techniques(grid: Grid) -> Counter[str]:
    res = rustoku.solve_steps(to_string(grid), "expert")
    return Counter() if res is None else Counter(s["technique"] for s in res["steps"])


def very_easy_givens(n: int) -> int:
    return {4: 8, 6: 18, 9: 40}[n]


def grade(grid: Grid) -> Level:
    n = len(grid)
    givens = sum(1 for row in grid for v in row if v)
    if logic_solve(grid, allow_hidden=False).solved:
        return "very_easy" if givens >= very_easy_givens(n) else "easy"
    if logic_solve(grid, allow_hidden=True).solved:
        return "easy"
    if n != 9:
        return "medium"
    for level, tset in zip(("medium", "hard"), RUSTOKU_SETS[:2], strict=True):
        if logical_at(grid, tset):
            return level  # type: ignore[return-value]
    return "expert"


def keeps_level(grid: Grid, target: Level) -> bool:
    """Is the grid still solvable without guessing using techniques up to `target`?"""
    n = len(grid)
    if target == "very_easy":
        return logic_solve(grid, allow_hidden=False).solved
    if target == "easy" or n != 9:
        return logic_solve(grid, allow_hidden=True).solved if target == "easy" else True
    if target == "expert":
        return True
    return logical_at(grid, target)


def band_distance(a: Level, b: Level) -> int:
    return abs(LEVELS.index(a) - LEVELS.index(b))
