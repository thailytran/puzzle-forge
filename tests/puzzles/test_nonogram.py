from __future__ import annotations

import pytest

from forge.core.models import PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.puzzles.cbn.font import ICONS
from forge.puzzles.nonogram import Nonogram, line_solve, runs


def _spec(name: str) -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "nonogram",
            "level": "medium",
            "audience": "adult",
            "constraints": [{"kind": "answer_is", "word": "@" + name}],
        }
    )


def test_runs() -> None:
    assert runs([0, 1, 1, 0, 1]) == [2, 1]
    assert runs([0, 0]) == [0]


@pytest.mark.parametrize("name", sorted(ICONS))
def test_every_evidence_picture_is_a_unique_nonogram(name: str) -> None:
    ng = Nonogram()
    pz = ng.generate(_spec(name), 3)
    assert pz.verify is not None and pz.verify.ok, pz.verify
    assert ng.solve(pz).solution["code"] == "@" + name
    assert ng.generate(_spec(name), 3).content_hash == pz.content_hash


def test_contradicting_clues_are_detected() -> None:
    assert line_solve([[3]], [[1], [1]], []) is None


def test_render_block() -> None:
    ng = Nonogram()
    pz = ng.generate(_spec("lantern"), 1)
    blk = ng.render(pz, RenderCtx(width_in=6, height_in=7)).blocks[1]
    assert blk["kind"] == "nonogram" and blk["grid"] is None and blk["cell_in"] > 0.2
