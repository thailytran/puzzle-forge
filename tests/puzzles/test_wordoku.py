from __future__ import annotations

import sys
import types

import pytest

from forge.core.models import PuzzleSpec


@pytest.fixture(autouse=True)
def _rustoku_stand_in():
    """rustoku is a compiled wheel; 4x4 / 6x6 wordoku never call it, so an empty stand-in
    module is enough where it is missing. Removed again so other tests still see it missing."""
    try:
        import rustoku  # noqa: F401

        yield
        return
    except ImportError:
        pass
    sys.modules["rustoku"] = types.ModuleType("rustoku")
    yield
    for m in ("rustoku", "forge.puzzles.sudoku.generator", "forge.puzzles.sudoku.grading"):
        sys.modules.pop(m, None)


def _w():  # imported inside the tests: the sudoku package needs rustoku (stand-in above)
    from forge.puzzles.wordoku import Wordoku, word_ok

    return Wordoku(), word_ok


def _spec(word: str, level: str = "easy", audience: str = "kids_9_12") -> PuzzleSpec:
    return PuzzleSpec.model_validate(
        {
            "type": "wordoku",
            "level": level,
            "audience": audience,
            "constraints": [{"kind": "answer_is", "word": word}],
        }
    )


@pytest.mark.parametrize("word", ["STAR", "WINTER", "CANDLE"])
def test_small_wordoku_is_unique_and_spells_the_word(word: str) -> None:
    w, _ok = _w()
    for seed in (1, 2, 3):
        pz = w.generate(_spec(word), seed)
        assert pz.verify is not None and pz.verify.ok and pz.verify.unique
        res = w.solve(pz)
        assert res.solution is not None and res.solution["word"] == word
        assert w.generate(_spec(word), seed).content_hash == pz.content_hash


def test_bad_words_are_refused() -> None:
    _w0, word_ok = _w()
    assert not word_ok("LANTERN")  # 7 letters
    assert not word_ok("LETTER")  # repeated letters
    assert word_ok("SNOWFLAKE")


def test_tampered_grid_fails_verification() -> None:
    w, _ok = _w()
    pz = w.generate(_spec("WINTER"), 5)
    g = [list(r) for r in pz.data["givens"]]
    for r, row in enumerate(g):  # blank every given of one row: more than one solution
        g[r] = ["" for _ in row] if r < 3 else row
    bad = pz.model_copy(update={"data": {**pz.data, "givens": g}})
    assert not w.verify(bad).ok


def test_render_shades_the_answer_row() -> None:
    w, _ok = _w()
    pz = w.generate(_spec("STAR", "easy", "kids_6_8"), 4)
    from forge.core.protocol import RenderCtx

    blk = w.render(pz, RenderCtx(width_in=5, height_in=5)).blocks[1]
    assert blk["kind"] == "sudoku_grid" and len(blk["shaded"]) == 4
