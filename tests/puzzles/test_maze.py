from __future__ import annotations

from pathlib import Path
from statistics import mean

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import LEVELS, PuzzleSpec
from forge.core.protocol import PuzzleType, RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.maze import Maze
from forge.puzzles.maze.grid import E, N, S, W, bfs_path

MZ = Maze()
CTX = RenderCtx(width_in=7.0, height_in=9.0)


def spec(level: str = "easy", audience: str = "adult", **kw: object) -> PuzzleSpec:
    data: dict[str, object] = {"type": "maze", "level": level, "audience": audience}
    data.update(kw)
    return PuzzleSpec.model_validate(data)


def test_is_puzzle_type() -> None:
    assert isinstance(MZ, PuzzleType)


def test_bfs_simple_corridor() -> None:
    # 1x3 corridor: (0,0) -E- (0,1) -E- (0,2)
    cells = [[E, E | W, W]]
    assert bfs_path(cells, (0, 0), (0, 2)) == [(0, 0), (0, 1), (0, 2)]
    assert bfs_path([[0, 0]], (0, 0), (0, 1)) is None
    assert N and S


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=0, max_value=2**32),
    level=st.sampled_from(LEVELS),
    audience=st.sampled_from(["kids_6_8", "kids_9_12", "adult", "senior_large_print"]),
)
def test_every_generated_maze_verifies(seed: int, level: str, audience: str) -> None:
    p = MZ.generate(spec(level, audience), seed)
    rep = MZ.verify(p)
    assert rep.ok, rep.messages
    assert rep.unique


def test_deterministic() -> None:
    assert (
        MZ.generate(spec("hard"), 9).model_dump_json()
        == MZ.generate(spec("hard"), 9).model_dump_json()
    )


def test_sizes_grow_with_level() -> None:
    sizes = [MZ.generate(spec(lvl), 1).data["rows"] for lvl in LEVELS]
    assert sizes == sorted(sizes)


def test_difficulty_increases() -> None:
    avg = {
        lvl: mean(MZ.generate(spec(lvl), s).difficulty.score for s in range(3))  # type: ignore[union-attr]
        for lvl in LEVELS
    }
    assert avg["very_easy"] < avg["easy"] < avg["medium"] < avg["hard"] < avg["expert"]


@pytest.mark.parametrize("level", LEVELS)
def test_adult_label_matches(level: str) -> None:
    p = MZ.generate(spec(level), 4)
    assert p.difficulty is not None
    assert p.difficulty.label == level


@pytest.mark.parametrize("seq", ["KEY", "HARBOR", "LIGHTHOUSE"])
def test_path_letters(seq: str) -> None:
    p = MZ.generate(spec("medium", constraints=[{"kind": "path_letters", "seq": seq}]), 3)
    assert p.token == seq
    path = [tuple(x) for x in p.solution["path"]]
    letters = {(x["r"], x["c"]): x["ch"] for x in p.data["letters"]}
    on_path = "".join(letters[c] for c in path if c in letters)
    assert on_path == seq
    assert len(letters) > len(seq)  # decoys exist
    assert MZ.verify(p).ok


def test_path_letters_too_long() -> None:
    with pytest.raises(GenerationError):
        MZ.generate(spec("very_easy", constraints=[{"kind": "path_letters", "seq": "A" * 200}]), 1)


def test_verify_detects_loop() -> None:
    p = MZ.generate(spec("easy"), 2)
    cells = [list(r) for r in p.data["cells"]]
    # knock down a wall that is still standing -> creates a loop (non-unique path)
    for r in range(len(cells)):
        for c in range(len(cells[0]) - 1):
            if not cells[r][c] & E:
                cells[r][c] |= E
                cells[r][c + 1] |= W
                bad = p.model_copy(update={"data": {**p.data, "cells": cells}})
                assert not MZ.verify(bad).ok
                return
    pytest.fail("no wall found")


def test_render() -> None:
    p = MZ.generate(spec("medium"), 2)
    rb = MZ.render(p, CTX)
    block = rb.blocks[0]
    assert block["kind"] == "maze"
    assert block["path"] in rb.files
    assert rb.files[block["path"]].startswith(b"<svg")
    sol = MZ.render_solution(p, CTX)
    assert b"polyline" in sol.files[sol.blocks[0]["path"]]


@pytest.mark.typst
def test_render_pdf(tmp_path: Path) -> None:
    from forge.puzzles.preview import preview_pdf

    p = MZ.generate(spec("medium", constraints=[{"kind": "path_letters", "seq": "KEY"}]), 2)
    assert preview_pdf(p, tmp_path / "p.pdf").stat().st_size > 1000
