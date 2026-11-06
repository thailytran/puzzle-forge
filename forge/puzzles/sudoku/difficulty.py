"""Sudoku difficulty score: band from the technique grade, position inside it from givens."""

from __future__ import annotations

from forge.core.models import LEVELS, DifficultyScore, Puzzle
from forge.puzzles.base import clamp01
from forge.puzzles.sudoku.grading import grade, techniques


def difficulty(puzzle: Puzzle) -> DifficultyScore:
    givens = [list(r) for r in puzzle.data["givens"]]
    n = len(givens)
    count = sum(1 for row in givens for v in row if v)
    ratio = count / (n * n)
    label = grade(givens)
    within = clamp01((0.6 - ratio) / (0.6 - 0.25))
    score = round(LEVELS.index(label) * 20 + 19.9 * within, 1)
    feats: dict[str, float] = {"givens": float(count), "givens_ratio": round(ratio, 3)}
    if n == 9:
        for tech, k in techniques(givens).items():
            feats[f"tech:{tech}"] = float(k)
    return DifficultyScore(score=score, label=label, features=feats)
