"""Word search difficulty score (0..100) from measurable features."""

from __future__ import annotations

from forge.core.models import DifficultyScore, Puzzle, level_from_score
from forge.puzzles.base import clamp01
from forge.puzzles.wordsearch.grid import MASKED
from forge.puzzles.wordsearch.params import BACKWARD, DIAGONAL

# score = BASE + SPAN * Σ weight·feature  (features are 0..1). Calibrated so the adult
# levels land in their bands of forge.core.models.level_from_score.
BASE, SPAN = 15.0, 82.0
WEIGHTS = {
    "area": 0.30,
    "directions": 0.25,
    "backwards": 0.15,
    "diagonal": 0.10,
    "word_count": 0.15,
    "overlap": 0.03,
    "decoys": 0.01,
    "letter_camouflage": 0.01,
}


def features(puzzle: Puzzle) -> dict[str, float]:
    rows: list[str] = puzzle.data["rows"]
    placements = puzzle.solution["placements"]
    n = max(len(placements), 1)
    active = sum(ch != MASKED for row in rows for ch in row)
    total_letters = sum(len(p["word"]) for p in placements)
    covered = {
        (p["row"] + i * dr, p["col"] + i * dc)
        for p in placements
        for i in range(len(p["word"]))
        for dr, dc in [_vec(p["dir"])]
    }
    return {
        "area": clamp01((active - 64) / (400 - 64)),
        "directions": clamp01((len(set(puzzle.data["directions"])) - 2) / 6),
        "backwards": sum(p["dir"] in BACKWARD for p in placements) / n,
        "diagonal": sum(p["dir"] in DIAGONAL for p in placements) / n,
        "word_count": clamp01((len(placements) - 6) / (32 - 6)),
        "overlap": clamp01((total_letters - len(covered)) / max(total_letters, 1) * 4),
        "decoys": clamp01(puzzle.data.get("decoys", 0) / 8),
        "letter_camouflage": float(puzzle.data.get("word_letter_fill", 0.0)),
    }


def _vec(d: str) -> tuple[int, int]:
    from forge.puzzles.wordsearch.params import DIRS

    return DIRS[d]


def difficulty(puzzle: Puzzle) -> DifficultyScore:
    f = features(puzzle)
    score = round(BASE + SPAN * sum(WEIGHTS[k] * f[k] for k in WEIGHTS), 1)
    return DifficultyScore(score=score, label=level_from_score(score), features=f)
