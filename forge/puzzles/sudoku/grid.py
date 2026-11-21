"""Pure-Python sudoku core (any N with rectangular boxes): solver, counter, singles logic.

This module is the *independent* solver used by `verify` — it shares no code with rustoku.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

Grid = list[list[int]]  # 0 = empty

BOX_SHAPES = {4: (2, 2), 6: (2, 3), 9: (3, 3)}


def box_shape(n: int) -> tuple[int, int]:
    if n not in BOX_SHAPES:
        raise ValueError(f"unsupported sudoku size {n}; use 4, 6 or 9")
    return BOX_SHAPES[n]


def parse(text: str, n: int) -> Grid:
    vals = [0 if ch in ".0_" else int(ch) for ch in text]
    if len(vals) != n * n:
        raise ValueError("bad sudoku string length")
    return [vals[i * n : (i + 1) * n] for i in range(n)]


def to_string(grid: Grid) -> str:
    return "".join(str(v) for row in grid for v in row)


def copy(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def _box_index(r: int, c: int, n: int) -> int:
    br, bc = box_shape(n)
    return (r // br) * (n // bc) + c // bc


def candidates(grid: Grid, r: int, c: int) -> set[int]:
    n = len(grid)
    br, bc = box_shape(n)
    used = set(grid[r]) | {grid[i][c] for i in range(n)}
    r0, c0 = r - r % br, c - c % bc
    used |= {grid[i][j] for i in range(r0, r0 + br) for j in range(c0, c0 + bc)}
    return set(range(1, n + 1)) - used


def is_valid_complete(grid: Grid) -> bool:
    n = len(grid)
    full = set(range(1, n + 1))
    rows_ok = all(set(row) == full for row in grid)
    cols_ok = all({grid[r][c] for r in range(n)} == full for c in range(n))
    boxes: dict[int, set[int]] = {}
    for r in range(n):
        for c in range(n):
            boxes.setdefault(_box_index(r, c, n), set()).add(grid[r][c])
    return rows_ok and cols_ok and all(b == full for b in boxes.values())


def givens_consistent(grid: Grid) -> bool:
    n = len(grid)
    for r in range(n):
        for c in range(n):
            v = grid[r][c]
            if v:
                grid[r][c] = 0
                ok = v in candidates(grid, r, c)
                grid[r][c] = v
                if not ok:
                    return False
    return True


def _search(grid: Grid, limit: int, rng: random.Random | None, out: list[Grid]) -> int:
    """Backtracking with minimum-remaining-values. Returns #solutions found (≤ limit)."""
    n = len(grid)
    best: tuple[int, int] | None = None
    best_cands: list[int] = []
    for r in range(n):
        for c in range(n):
            if grid[r][c] == 0:
                cands = sorted(candidates(grid, r, c))
                if not cands:
                    return 0
                if best is None or len(cands) < len(best_cands):
                    best, best_cands = (r, c), cands
                    if len(cands) == 1:
                        break
        if best is not None and len(best_cands) == 1:
            break
    if best is None:
        out.append(copy(grid))
        return 1
    if rng is not None:
        rng.shuffle(best_cands)
    r, c = best
    found = 0
    for v in best_cands:
        grid[r][c] = v
        found += _search(grid, limit - found, rng, out)
        grid[r][c] = 0
        if found >= limit:
            break
    return found


def count_solutions(grid: Grid, limit: int = 2) -> int:
    if not givens_consistent(grid):
        return 0
    return _search(copy(grid), limit, None, [])


def solve(grid: Grid) -> Grid | None:
    out: list[Grid] = []
    if givens_consistent(grid) and _search(copy(grid), 1, None, out):
        return out[0]
    return None


def random_full_grid(n: int, rng: random.Random, fixed: dict[tuple[int, int], int]) -> Grid | None:
    grid = [[0] * n for _ in range(n)]
    for (r, c), v in fixed.items():
        grid[r][c] = v
    if not givens_consistent(grid):
        return None
    out: list[Grid] = []
    return out[0] if _search(grid, 1, rng, out) else None


@dataclass
class LogicResult:
    solved: bool
    naked: int
    hidden: int
    grid: Grid


def logic_solve(grid: Grid, allow_hidden: bool = True) -> LogicResult:
    """Fill using only naked singles (+ hidden singles). Used to grade easy puzzles."""
    g = copy(grid)
    n = len(g)
    br, bc = box_shape(n)
    naked = hidden = 0
    progress = True
    while progress:
        progress = False
        cand = {(r, c): candidates(g, r, c) for r in range(n) for c in range(n) if g[r][c] == 0}
        for (r, c), cs in cand.items():
            if len(cs) == 1:
                g[r][c] = next(iter(cs))
                naked += 1
                progress = True
        if progress or not allow_hidden:
            continue
        units: list[list[tuple[int, int]]] = []
        units += [[(r, c) for c in range(n)] for r in range(n)]
        units += [[(r, c) for r in range(n)] for c in range(n)]
        units += [
            [(r, c) for r in range(R, R + br) for c in range(C, C + bc)]
            for R in range(0, n, br)
            for C in range(0, n, bc)
        ]
        for unit in units:
            for v in range(1, n + 1):
                spots = [cell for cell in unit if cell in cand and v in cand[cell]]
                if len(spots) == 1:
                    r, c = spots[0]
                    if g[r][c] == 0:
                        g[r][c] = v
                        hidden += 1
                        progress = True
            if progress:
                break
    solved = all(v for row in g for v in row)
    return LogicResult(solved, naked, hidden, g)
