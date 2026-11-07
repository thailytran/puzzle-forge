"""Growing-tree maze generator (perfect maze → exactly one route from start to finish).

`river` = probability of extending the newest cell (long winding corridors, recursive
backtracker) vs. a random active cell (many short dead ends, Prim-like). Lower = harder.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, replace

from forge.core.models import Audience, Level, PathLetters, PuzzleSpec
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.maze.grid import DELTA, OPP, Cell, Cells, bfs_path


@dataclass(frozen=True)
class MzParams:
    rows: int
    cols: int
    river: float


_BY_LEVEL: dict[Level, MzParams] = {
    "very_easy": MzParams(8, 8, 0.95),
    "easy": MzParams(12, 12, 0.8),
    "medium": MzParams(20, 20, 0.55),
    "hard": MzParams(32, 32, 0.3),
    "expert": MzParams(42, 42, 0.1),
}
_CAP: dict[Audience, int] = {"kids_6_8": 14, "kids_9_12": 22, "senior_large_print": 26}


def resolve_params(spec: PuzzleSpec) -> MzParams:
    p = _BY_LEVEL[spec.level]
    cap = _CAP.get(spec.audience)
    if cap:
        p = replace(p, rows=min(p.rows, cap), cols=min(p.cols, cap))
    if spec.size:
        p = replace(p, rows=spec.size[0], cols=spec.size[1])
    if "river" in spec.options:
        p = replace(p, river=float(spec.options["river"]))
    return p


def carve(p: MzParams, rng: random.Random) -> Cells:
    cells = [[0] * p.cols for _ in range(p.rows)]
    start = (rng.randrange(p.rows), rng.randrange(p.cols))
    visited = {start}
    active: list[Cell] = [start]
    dirs = list(DELTA)
    while active:
        i = len(active) - 1 if rng.random() < p.river else rng.randrange(len(active))
        r, c = active[i]
        rng.shuffle(dirs)
        for d in dirs:
            dr, dc = DELTA[d]
            rr, cc = r + dr, c + dc
            if 0 <= rr < p.rows and 0 <= cc < p.cols and (rr, cc) not in visited:
                cells[r][c] |= d
                cells[rr][cc] |= OPP[d]
                visited.add((rr, cc))
                active.append((rr, cc))
                break
        else:
            active.pop(i)
    return cells


def entrance_exit(p: MzParams) -> tuple[Cell, Cell]:
    return (0, 0), (p.rows - 1, p.cols - 1)


def place_letters(
    spec: PuzzleSpec, path: list[Cell], p: MzParams, rng: random.Random
) -> list[dict[str, object]]:
    pl = find_constraint(spec, PathLetters)
    if pl is None:
        return []
    seq = "".join(ch for ch in pl.seq.upper() if ch.isalnum())
    inner = path[1:-1]
    if len(seq) == 0 or len(inner) < 2 * len(seq):
        raise GenerationError(f"path_letters: route of {len(path)} cells too short for {seq!r}")
    step = len(inner) / (len(seq) + 1)
    chosen = [inner[round((i + 1) * step) - 1] for i in range(len(seq))]
    letters = [{"r": r, "c": c, "ch": ch} for (r, c), ch in zip(chosen, seq, strict=True)]
    on_path = set(path)
    off = [(r, c) for r in range(p.rows) for c in range(p.cols) if (r, c) not in on_path]
    rng.shuffle(off)
    n_decoys = min(len(off), max(3, len(seq)))
    pool = seq + string.ascii_uppercase
    for r, c in off[:n_decoys]:
        letters.append({"r": r, "c": c, "ch": pool[rng.randrange(len(pool))]})
    return sorted(letters, key=lambda x: (int(str(x["r"])), int(str(x["c"]))))


def build(
    spec: PuzzleSpec, rng: random.Random
) -> tuple[Cells, list[Cell], list[dict[str, object]]]:
    p = resolve_params(spec)
    cells = carve(p, rng)
    start, goal = entrance_exit(p)
    path = bfs_path(cells, start, goal)
    if path is None:  # cannot happen for a perfect maze
        raise GenerationError("maze: no route")
    return cells, path, place_letters(spec, path, p, rng)
