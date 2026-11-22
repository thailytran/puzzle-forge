from __future__ import annotations

import itertools

import pytest

from forge.core.models import PuzzleSpec
from forge.puzzles.wordladder import WordLadder, ladders
from forge.wordlists import is_blocked
from forge.wordlists.dictionary import is_word


def _spec(word: str, level: str = "medium") -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "wordladder",
            "level": level,
            "audience": "adult",
            "constraints": [{"kind": "answer_is", "word": word}],
        }
    )


@pytest.mark.parametrize("word", ["BELL", "ROPE", "NOTE", "BOOT", "PAW"])
def test_unique_ladder_through_the_keyword(word: str) -> None:
    wl = WordLadder()
    pz = wl.generate(_spec(word), 1)
    assert pz.verify is not None and pz.verify.ok and pz.verify.unique
    lad = pz.solution["ladder"]
    assert lad[pz.data["key_rung"]] == word
    for a, b in itertools.pairwise(lad):
        assert sum(x != y for x, y in zip(a, b, strict=True)) == 1
    assert all(is_word(w) and not is_blocked(w) for w in lad)
    assert wl.generate(_spec(word), 1).content_hash == pz.content_hash


def test_ladders_counts_all_dictionary_paths() -> None:
    assert ladders("CAT", "COT", [1], 5) == [["CAT", "COT"]]
