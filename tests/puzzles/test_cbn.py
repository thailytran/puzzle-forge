from __future__ import annotations

import itertools
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import PuzzleSpec
from forge.core.protocol import PuzzleType
from forge.puzzles.base import GenerationError
from forge.puzzles.cbn import ColorByNumber, eval_expr, read_code
from forge.puzzles.cbn.font import GLYPHS
from forge.qa.solvers2 import SOLVERS, matches_stored

CB = ColorByNumber()


def spec(level: str = "easy", audience: str = "adult", **kw: object) -> PuzzleSpec:
    data: dict[str, object] = {"type": "cbn", "level": level, "audience": audience}
    data.update(kw)
    return PuzzleSpec.model_validate(data)


def test_type() -> None:
    assert isinstance(CB, PuzzleType)


def test_glyphs_distinct() -> None:
    dist = min(
        sum(
            a != b
            for ra, rb in zip(GLYPHS[x], GLYPHS[y], strict=True)
            for a, b in zip(ra, rb, strict=True)
        )
        for x, y in itertools.combinations(GLYPHS, 2)
    )
    assert dist >= 2


@pytest.mark.parametrize("e,v", [("3+4", 7), ("19-7", 12), ("3x5", 15)])
def test_eval(e: str, v: int) -> None:
    assert eval_expr(e) == v


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(0, 2**32),
    level=st.sampled_from(["very_easy", "easy", "medium", "hard"]),
    audience=st.sampled_from(["kids_6_8", "adult", "senior_large_print"]),
)
def test_every_mosaic_reveals_its_code(seed: int, level: str, audience: str) -> None:
    p = CB.generate(spec(level, audience), seed)
    assert CB.verify(p).ok
    assert read_code(p.solution["colors"]) == p.solution["code"] == p.token
    count, sol = SOLVERS["cbn"](p)
    assert count == 1 and matches_stored(p, sol)


@pytest.mark.parametrize("code", ["7", "K", "47", "K7", "OWL"])
def test_answer_is_code(code: str) -> None:
    p = CB.generate(spec("hard", constraints=[{"kind": "answer_is", "word": code}]), 1)
    assert p.solution["code"] == code


def test_type_b_cells_are_sums() -> None:
    p = CB.generate(spec("medium"), 2)
    assert p.data["mode"] == "B"
    answers = {e["answer"] for e in p.data["palette"]}
    assert all(eval_expr(c) in answers for row in p.data["cells"] for c in row)


def test_tamper_changes_code() -> None:
    p = CB.generate(spec("easy"), 4)
    cells = [list(r) for r in p.data["cells"]]
    for r, row in enumerate(cells):  # repaint every code cell as background
        cells[r] = ["2" if v == "1" else v for v in row]
    bad = p.model_copy(update={"data": {**p.data, "cells": cells}})
    assert not CB.verify(bad).ok


def test_unsupported_code() -> None:
    with pytest.raises(GenerationError):
        CB.generate(spec("easy", options={"code": "4?"}), 1)


@pytest.mark.typst
def test_render_pdf(tmp_path: Path) -> None:
    from forge.puzzles.preview import preview_pdf

    for lvl in ("easy", "medium"):
        assert preview_pdf(CB.generate(spec(lvl), 3), tmp_path / f"{lvl}.pdf").stat().st_size > 1000
