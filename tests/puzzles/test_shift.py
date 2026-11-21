from __future__ import annotations

import pytest

from forge.core.models import PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.shift import Shift, move
from forge.qa.solvers2 import SOLVERS, matches_stored

TEXT = "The ferryman wrote in his log that the river gate was frozen from dusk to dawn"


def spec(text: str = TEXT, word: str = "FROZEN") -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "shift",
            "level": "medium",
            "audience": "adult",
            "options": {"text": text},
            "constraints": [{"kind": "answer_is", "word": word}],
        }
    )


def test_every_seed_gives_one_reading() -> None:
    sh = Shift()
    for seed in range(60):
        p = sh.generate(spec(), seed)
        assert sh.verify(p).ok and p.token == "FROZEN"
        assert "FROZEN" not in p.data["cipher"].split()
        assert sh.solve(p).solution == p.solution
        assert matches_stored(p, SOLVERS["shift"](p)[1])
        assert p.content_hash == sh.generate(spec(), seed).content_hash
    assert len(sh.render(p, RenderCtx(7.0, 9.0)).blocks) >= 5


def test_rejects_bad_messages() -> None:
    sh = Shift()
    with pytest.raises(GenerationError):
        sh.generate(spec("Too short to hide"), 1)
    with pytest.raises(GenerationError):
        sh.generate(spec(word="MELTED"), 1)
    with pytest.raises(GenerationError):  # not dictionary words: no reading can be proved
        sh.generate(spec("Zxq the frozen gate was shut by qqv from dusk to dawn"), 1)
    p = sh.generate(spec(), 2)
    bad = p.model_copy(update={"data": {"cipher": move(p.data["cipher"], 1)}})
    assert sh.verify(bad).ok is False or sh.solve(bad).solution != p.solution
