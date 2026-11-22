from __future__ import annotations

import itertools
import random

import pytest

from forge.core.models import PuzzleSpec
from forge.puzzles.lightup import LightUp, _nbrs, _seen, solve_all


def _brute(g: list[list[str]]) -> int:
    """Count solutions by trying every lantern subset (tiny grids only)."""
    whites = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == "."]
    n = 0
    for k in range(len(whites) + 1):
        for lamps in itertools.combinations(whites, k):
            s = set(lamps)
            if any(x in s for w in lamps for x in _seen(g, *w)[1:]):
                continue
            if any(not any(x in s for x in _seen(g, *w)) for w in whites):
                continue
            if any(
                sum(1 for x in _nbrs(g, r, c) if x in s) != int(v)
                for r, row in enumerate(g)
                for c, v in enumerate(row)
                if v.isdigit()
            ):
                continue
            n += 1
    return n


def test_solver_matches_brute_force_on_small_grids() -> None:
    rng = random.Random(7)
    for _ in range(40):
        g = [[rng.choice(".....#0123") for _ in range(4)] for _ in range(4)]
        assert len(solve_all(g, 99)) == _brute(g)


@pytest.mark.parametrize(
    ("level", "audience"), [("easy", "kids_9_12"), ("medium", "adult"), ("hard", "adult")]
)
def test_generated_grids_are_unique(level: str, audience: str) -> None:
    lu = LightUp()
    spec = PuzzleSpec.model_validate({"type": "lightup", "level": level, "audience": audience})
    for seed in (1, 2, 3):
        pz = lu.generate(spec, seed)
        assert pz.verify is not None and pz.verify.ok and pz.verify.unique
        assert lu.generate(spec, seed).content_hash == pz.content_hash


def test_lantern_count_is_the_code() -> None:
    lu = LightUp()
    spec = PuzzleSpec.model_validate(
        {
            "type": "lightup",
            "level": "medium",
            "audience": "adult",
            "constraints": [{"kind": "answer_is", "word": "11"}],
        }
    )
    pz = lu.generate(spec, 4)
    assert pz.solution["code"] == "11" and len(pz.solution["lamps"]) == 11
