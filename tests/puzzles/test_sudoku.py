from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import PuzzleSpec
from forge.core.protocol import PuzzleType, RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.sudoku import Sudoku
from forge.puzzles.sudoku.grid import box_shape, count_solutions, logic_solve, parse

SD = Sudoku()
CTX = RenderCtx(width_in=7.0, height_in=9.0)


def spec(level: str = "easy", audience: str = "adult", **kw: object) -> PuzzleSpec:
    data: dict[str, object] = {"type": "sudoku", "level": level, "audience": audience}
    data.update(kw)
    return PuzzleSpec.model_validate(data)


def test_is_puzzle_type() -> None:
    assert isinstance(SD, PuzzleType)


def test_box_shapes() -> None:
    assert box_shape(4) == (2, 2)
    assert box_shape(6) == (2, 3)
    assert box_shape(9) == (3, 3)


def test_count_solutions_empty_grid_multiple() -> None:
    assert count_solutions([[0] * 4 for _ in range(4)], limit=2) == 2


def test_logic_solver_singles() -> None:
    grid = parse("1234341221434321".replace("4", "0", 2), 4)
    res = logic_solve(grid)
    assert res.solved


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=0, max_value=2**32),
    level=st.sampled_from(["very_easy", "easy", "medium"]),
    audience=st.sampled_from(["kids_6_8", "kids_9_12", "adult", "senior_large_print"]),
)
def test_every_generated_puzzle_verifies(seed: int, level: str, audience: str) -> None:
    p = SD.generate(spec(level, audience), seed)
    rep = SD.verify(p)
    assert rep.ok, rep.messages
    assert rep.unique


@pytest.mark.parametrize("size", [4, 6, 9])
def test_sizes(size: int) -> None:
    p = SD.generate(spec("easy", options={"size": size}), 3)
    assert p.data["size"] == size
    assert len(p.data["givens"]) == size
    assert SD.verify(p).ok


@pytest.mark.parametrize("level", ["very_easy", "easy", "medium", "hard", "expert"])
def test_adult_levels_labelled(level: str) -> None:
    p = SD.generate(spec(level), 11)
    assert SD.verify(p).ok
    assert p.difficulty is not None
    order = ["very_easy", "easy", "medium", "hard", "expert"]
    # label is honest (from the technique trace) and within one band of the request
    assert abs(order.index(p.difficulty.label) - order.index(level)) <= 1


def test_kids_small_grid() -> None:
    p = SD.generate(spec("easy", "kids_6_8"), 1)
    assert p.data["size"] == 4


def test_deterministic() -> None:
    a = SD.generate(spec("medium"), 42)
    b = SD.generate(spec("medium"), 42)
    assert a.model_dump_json() == b.model_dump_json()


def test_shaded_cells_constraint() -> None:
    cells = [[0, 0], [4, 4], [8, 8]]
    p = SD.generate(
        spec("easy", constraints=[{"kind": "shaded_cells", "cells": cells, "expect": "472"}]), 5
    )
    sol = p.solution["grid"]
    assert "".join(str(sol[r][c]) for r, c in cells) == "472"
    assert all(p.data["givens"][r][c] == 0 for r, c in cells)
    assert p.token == "472"
    assert SD.verify(p).ok


def test_shaded_cells_impossible() -> None:
    bad = {"kind": "shaded_cells", "cells": [[0, 0], [0, 1]], "expect": "55"}
    with pytest.raises(GenerationError):
        SD.generate(spec("easy", constraints=[bad]), 1)


def test_verify_detects_non_unique() -> None:
    p = SD.generate(spec("easy", options={"size": 4}), 2)
    empty = [[0] * 4 for _ in range(4)]
    bad = p.model_copy(update={"data": {**p.data, "givens": empty}})
    rep = SD.verify(bad)
    assert not rep.ok
    assert rep.unique is False


def test_render_blocks() -> None:
    p = SD.generate(spec("easy"), 2)
    b = SD.render(p, CTX).blocks[0]
    assert b["kind"] == "sudoku_grid"
    assert b["box_rows"] == 3
    s = SD.render_solution(p, CTX).blocks[0]
    assert all(v for row in s["cells"] for v in row)


@pytest.mark.typst
def test_render_pdf(tmp_path: Path) -> None:
    from forge.puzzles.preview import preview_pdf

    p = SD.generate(
        spec("easy", constraints=[{"kind": "shaded_cells", "cells": [[1, 1]], "expect": "7"}]), 2
    )
    assert preview_pdf(p, tmp_path / "p.pdf").stat().st_size > 1000
