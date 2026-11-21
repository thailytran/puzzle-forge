from __future__ import annotations

import itertools
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import PuzzleSpec
from forge.core.protocol import PuzzleType, RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.cbn import ColorByNumber, eval_expr, min_cell_mm, read_code, tiling, tiling_of
from forge.puzzles.cbn.font import GLYPHS
from forge.qa.l2 import cbn_cell_findings
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


# --- cell shapes (one core: tiling + raster verifier) ---------------------------------------

SHAPES = ("square", "hex", "triangle", "circle")
LETTER = RenderCtx(width_in=7.0, height_in=9.0)


def shaped(shape: str, level: str = "easy", audience: str = "adult", **opts: object) -> PuzzleSpec:
    return spec(level, audience, options={"shape": shape, **opts})


def test_legacy_square_is_untouched() -> None:
    p = CB.generate(spec("easy"), 5)
    assert "shape" not in p.data and CB.verify(p).ok


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("level", ["very_easy", "easy", "medium", "hard"])
def test_every_shape_verifies(shape: str, level: str) -> None:
    for seed in range(4):
        p = CB.generate(shaped(shape, level), seed)
        t = tiling_of(p)
        assert p.data["shape"] == shape and len(p.data["cells"][0]) == len(t.cells)
        rep = CB.verify(p)
        assert rep.ok, rep
        colors = p.solution["colors"][0]
        code = p.solution["code"]
        assert tiling.read_raster(t, colors) == code  # shape-independent verifier
        assert tiling.read_centres(t, colors) == code  # independent second reading
        assert matches_stored(p, SOLVERS["cbn"](p)[1])


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(0, 10**6),
    shape=st.sampled_from(SHAPES),
    digit=st.sampled_from("0123456789"),
)
def test_any_digit_reveals_in_any_shape(seed: int, shape: str, digit: str) -> None:
    p = CB.generate(shaped(shape, "easy", code=digit), seed)
    assert CB.verify(p).ok and CB.solve(p).solution["code"] == digit


@pytest.mark.parametrize("shape", SHAPES)
def test_deterministic_per_shape(shape: str) -> None:
    a, b = CB.generate(shaped(shape), 11), CB.generate(shaped(shape), 11)
    assert a.content_hash == b.content_hash and a.data == b.data


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("audience", ["adult", "kids_9_12"])
def test_min_cell_size_on_letter(shape: str, audience: str) -> None:
    if shape == "triangle" and audience == "kids_9_12":
        with pytest.raises(GenerationError):  # an 8 mm triangle mosaic cannot hold a glyph
            CB.generate(shaped(shape, "hard", audience), 1)
        return
    for level in ("easy", "hard"):
        blk = CB.render(CB.generate(shaped(shape, level, audience), 1), LETTER).blocks[1]
        assert blk["kind"] == "cbn_poly" and blk["min_mm"] == min_cell_mm(audience)
        assert blk["cell_mm"] >= blk["min_mm"] and blk["font_pt"] >= 6.0
        assert cbn_cell_findings(1, [blk]) == []


def test_qa_flags_small_cells() -> None:
    small = RenderCtx(width_in=3.0, height_in=4.0)
    blk = CB.render(CB.generate(shaped("hex", "hard"), 1), small).blocks[1]
    assert blk["cell_mm"] < 5.0
    assert cbn_cell_findings(7, [blk])[0].evidence["page"] == 7


@pytest.mark.parametrize("shape", ["hex", "triangle", "circle"])
def test_tamper_is_caught_in_every_shape(shape: str) -> None:
    p = CB.generate(shaped(shape, code="8"), 2)
    colors = list(p.solution["colors"][0])
    on = [i for i, v in enumerate(colors) if v == 1]
    for i in on[: len(on) // 3]:
        colors[i] = 2
    assert tiling.read_raster(tiling_of(p), colors) != "8"


def test_mode_b_only_where_a_sum_fits() -> None:
    p = CB.generate(shaped("hex", "hard", mode="B", code="7"), 3)
    assert p.data["mode"] == "B" and CB.verify(p).ok
    assert CB.render(p, LETTER).blocks[1]["font_pt"] >= 6.0
    # a two-character code leaves no room for 7.2 mm cells: falls back to plain numbers
    assert CB.generate(shaped("hex", "hard", mode="B", code="47"), 3).data["mode"] == "A"
    assert CB.generate(shaped("triangle", "hard", mode="B"), 3).data["mode"] == "A"


def test_unknown_shape_and_long_code() -> None:
    with pytest.raises(GenerationError):
        CB.generate(shaped("star"), 1)
    with pytest.raises(GenerationError):
        CB.generate(shaped("triangle", code="OWL"), 1)


def test_tiling_geometry() -> None:
    for shape in SHAPES:
        t = tiling.make(shape, 6, 8)
        assert len(t.cells) == 48
        assert all(0 <= c.cx <= t.width and 0 <= c.cy <= t.height for c in t.cells)
        pts = [pt for c in t.cells for pt in c.pts]
        assert all(-1e-6 <= x <= t.width + 1e-6 and -1e-6 <= y <= t.height + 1e-6 for x, y in pts)


@pytest.mark.typst
@pytest.mark.parametrize("shape", SHAPES)
def test_render_pdf_shapes(tmp_path: Path, shape: str) -> None:
    from forge.puzzles.preview import preview_pdf

    p = CB.generate(shaped(shape, "medium"), 3)
    assert preview_pdf(p, tmp_path / f"{shape}.pdf").stat().st_size > 1000


@pytest.mark.parametrize("shape", ["square", "hex", "circle"])
def test_picture_codes_reveal_in_every_fitting_shape(shape: str) -> None:
    from forge.puzzles.cbn import tiling, tiling_of
    from forge.puzzles.cbn.font import ICON, ICONS

    assert all(len(r) == ICON and all(len(x) == ICON for x in r) for r in ICONS.values())
    cb = ColorByNumber()
    for name in ICONS:
        spec = PuzzleSpec.model_validate(
            {
                "type": "cbn",
                "level": "hard",
                "audience": "adult",
                "options": {"shape": shape},
                "constraints": [{"kind": "answer_is", "word": "@" + name}],
            }
        )
        p = cb.generate(spec, 5)
        t, colours = tiling_of(p), p.solution["colors"][0]
        assert cb.verify(p).ok and p.solution["code"] == "@" + name
        assert tiling.read_raster(t, colours) == tiling.read_centres(t, colours) == "@" + name
