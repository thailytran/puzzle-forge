"""Maze difficulty from size, route length, dead ends and junctions on the route."""

from __future__ import annotations

from forge.core.models import DifficultyScore, Puzzle, level_from_score
from forge.puzzles.base import clamp01
from forge.puzzles.maze.grid import Cells, dead_ends, degree

BASE, SPAN = 4.0, 84.0
WEIGHTS = {"area": 0.9, "route": 0.033, "dead_ends": 0.033, "junctions": 0.034}


def features(puzzle: Puzzle) -> dict[str, float]:
    cells: Cells = puzzle.data["cells"]
    n = len(cells) * len(cells[0])
    path = puzzle.solution["path"]
    junctions = sum(degree(cells, r, c) >= 3 for r, c in path)
    return {
        "area": clamp01((n - 64) / (1764 - 64)) ** 0.5,
        "route": clamp01(len(path) / n * 3),
        "dead_ends": clamp01(dead_ends(cells) / n * 3),
        "junctions": clamp01(junctions / max(len(path), 1) * 2.5),
    }


def difficulty(puzzle: Puzzle) -> DifficultyScore:
    f = features(puzzle)
    score = round(BASE + SPAN * sum(WEIGHTS[k] * f[k] for k in WEIGHTS), 1)
    return DifficultyScore(score=min(score, 100.0), label=level_from_score(score), features=f)
