from __future__ import annotations

from forge.core.models import PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.puzzles.cbn import PICTURE_MIN_MM, ColorByNumber, read_picture
from forge.puzzles.cbn.pictures import PICTURE_H, PICTURE_PALETTE, PICTURE_W, PICTURES


def _spec(name: str, shape: str = "square") -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "cbn",
            "level": "medium",
            "audience": "adult",
            "options": {"shape": shape, "mode": "A"},
            "constraints": [{"kind": "answer_is", "word": "#" + name}],
        }
    )


def test_every_picture_has_the_grid_size_and_known_colours() -> None:
    digits = {str(i + 1) for i in range(len(PICTURE_PALETTE))}
    for name, rows in PICTURES.items():
        assert len(rows) == PICTURE_H, name
        assert all(len(r) == PICTURE_W and set(r) <= digits for r in rows), name
    assert len({rows for rows in PICTURES.values()}) == len(PICTURES)  # no two pictures alike


def test_picture_mosaic_generates_solves_and_names_itself() -> None:
    cb = ColorByNumber()
    for name in PICTURES:
        for shape in ("square", "circle"):
            pz = cb.generate(_spec(name, shape), seed=7)
            assert pz.verify is not None and pz.verify.ok, (name, pz.verify)
            res = cb.solve(pz)
            assert res.solution is not None and res.solution["code"] == "#" + name
            assert cb.generate(_spec(name, shape), seed=7).content_hash == pz.content_hash


def test_a_wrong_cell_is_not_a_known_picture() -> None:
    rows = PICTURES["lantern"]
    flat = [int(c) for r in rows for c in r]
    assert read_picture(flat, PICTURE_H, PICTURE_W) == "#lantern"
    flat[40] = flat[40] % len(PICTURE_PALETTE) + 1
    assert read_picture(flat, PICTURE_H, PICTURE_W) == "?"


def test_picture_cells_stay_at_or_above_the_floor_in_the_designed_panel() -> None:
    cb = ColorByNumber()
    pz = cb.generate(_spec("scarf"), seed=1)
    blk = cb.render(pz, RenderCtx(width_in=5.07, height_in=4.13)).blocks[1]
    assert blk["cell_mm"] >= PICTURE_MIN_MM


def test_answer_picture_has_the_puzzle_cell_size() -> None:
    cb = ColorByNumber()
    pz = cb.generate(_spec("boot"), seed=3)
    ctx = RenderCtx(width_in=5.07, height_in=4.13)
    front = cb.render(pz, ctx).blocks[1]
    back = next(b for b in cb.render_solution(pz, ctx).blocks if b["kind"] == "cbn_poly")
    assert back["cell_mm"] == front["cell_mm"] and back["w_in"] == front["w_in"]
