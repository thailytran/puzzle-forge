from __future__ import annotations

import pytest

from forge.core.models import PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.numlock import NumLock, run
from forge.puzzles.registry import get_puzzle_type
from forge.qa.solvers2 import SOLVERS, matches_stored


def spec(code: str, level: str = "medium", audience: str = "adult") -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "numlock",
            "level": level,
            "audience": audience,
            "constraints": [{"kind": "answer_is", "word": code}],
        }
    )


@pytest.mark.parametrize("level", ["easy", "medium", "hard", "expert"])
@pytest.mark.parametrize("audience", ["adult", "kids_6_8"])
def test_every_generated_lock_verifies(level: str, audience: str) -> None:
    nl = NumLock()
    for seed in range(40):
        code = f"{(seed * 7919) % 10000:04d}"[: 2 + seed % 3]
        p = nl.generate(spec(code, level, audience), seed)
        assert nl.verify(p).ok and p.token == code
        assert nl.solve(p).solution == {"code": code}
        assert matches_stored(p, SOLVERS["numlock"](p)[1])
        assert all(len(d["steps"]) >= 2 and d["start"] >= 2 for d in p.data["dials"])
        assert p.content_hash == nl.generate(spec(code, level, audience), seed).content_hash


def test_bad_codes_and_tampering() -> None:
    nl = NumLock()
    with pytest.raises(GenerationError):
        nl.generate(spec("12A"), 1)
    p = nl.generate(spec("407"), 3)
    bad = p.model_copy(deep=True)
    bad.data["dials"][0]["steps"][-1][1] += 1
    assert not nl.verify(bad).ok
    assert run({"start": 7, "steps": [["/", 2]]}) is None
    assert len(nl.render(p, RenderCtx(7.0, 9.0)).blocks) == 3


def test_registered() -> None:
    assert get_puzzle_type("numlock").name == "numlock"
