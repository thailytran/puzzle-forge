from __future__ import annotations

import itertools

import pytest

from forge.core.models import PuzzleSpec
from forge.puzzles.starbattle import StarBattle, count_solutions


def _spec(word: str) -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "starbattle",
            "level": "medium",
            "audience": "adult",
            "constraints": [{"kind": "answer_is", "word": word}],
        }
    )


@pytest.mark.parametrize("word", ["SCARF", "LANTERN", "WOOLLEN", "SNOWFALL", "STARLIGHT"])
def test_unique_and_spells_the_word(word: str) -> None:
    sb = StarBattle()
    for seed in (1, 2):
        pz = sb.generate(_spec(word), seed)
        assert pz.verify is not None and pz.verify.ok and pz.verify.unique
        assert sb.solve(pz).solution["word"] == word
        stars = pz.solution["stars"]
        assert sorted(stars) == list(range(len(word)))
        assert all(abs(a - b) > 1 for a, b in itertools.pairwise(stars))
        assert sb.generate(_spec(word), seed).content_hash == pz.content_hash


def test_one_region_grid_has_no_solution() -> None:
    assert count_solutions([[0] * 5 for _ in range(5)])[0] == 0
