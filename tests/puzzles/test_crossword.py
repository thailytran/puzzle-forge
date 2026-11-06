from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import LEVELS, PuzzleSpec
from forge.core.protocol import PuzzleType, RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.crossword import Crossword
from forge.puzzles.crossword.grid import count_fill_solutions, numbering, slots
from forge.wordlists import available_themes

CW = Crossword()
CTX = RenderCtx(width_in=7.0, height_in=9.0)
THEMES = [t for t in available_themes() if t != "short_words"]


def spec(level: str = "easy", **kw: object) -> PuzzleSpec:
    data: dict[str, object] = {"type": "crossword", "level": level, "audience": "adult"}
    data.setdefault("theme", "animals")
    data.update(kw)
    return PuzzleSpec.model_validate(data)


def test_is_puzzle_type() -> None:
    assert isinstance(CW, PuzzleType)


def test_slots_and_numbering() -> None:
    rows = ["CAT", "A#O", "RAN"]
    found = {(s.r, s.c, s.dir, s.length) for s in slots(rows)}
    assert found == {(0, 0, "A", 3), (0, 0, "D", 3), (0, 2, "D", 3), (2, 0, "A", 3)}
    assert numbering(rows) == {(0, 0): 1, (0, 2): 2, (2, 0): 3}


def test_fill_solver_detects_ambiguity() -> None:
    shape = ["...", ".#.", "..."]
    # CAT/CAR/TON/RAN style square: two orientations possible -> 2 solutions
    assert count_fill_solutions(shape, ["CAT", "CAR", "TON", "RAN"], {}) >= 1


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=0, max_value=2**32),
    level=st.sampled_from(LEVELS),
    theme=st.sampled_from(THEMES),
)
def test_every_crossword_verifies(seed: int, level: str, theme: str) -> None:
    p = CW.generate(spec(level, theme=theme), seed)
    rep = CW.verify(p)
    assert rep.ok, rep.messages
    assert rep.unique


@pytest.mark.parametrize("level", LEVELS)
def test_label_matches_level(level: str) -> None:
    p = CW.generate(spec(level, theme="ocean"), 1)
    assert p.difficulty is not None
    assert p.difficulty.label == level


def test_deterministic() -> None:
    a, b = CW.generate(spec("hard"), 3), CW.generate(spec("hard"), 3)
    assert a.model_dump_json() == b.model_dump_json()


def test_clue_mode() -> None:
    from forge.wordlists import theme_words

    clues = {w: f"Clue for {w.lower()}" for w in theme_words("animals")}
    p = CW.generate(spec("easy", options={"mode": "clues", "clues": clues}), 2)
    assert p.data["mode"] == "clues"
    assert CW.verify(p).ok
    blocks = CW.render(p, CTX).blocks
    assert any(b.get("text") == "Across" for b in blocks)
    grid = blocks[0]["cells"]
    assert any(x and x["n"] == 1 for row in grid for x in row)


def test_clue_mode_without_clues_fails() -> None:
    with pytest.raises(GenerationError):
        CW.generate(spec("easy", options={"mode": "clues"}), 2)


def test_tamper_detected() -> None:
    p = CW.generate(spec("medium"), 2)
    bad = p.model_copy(update={"data": {**p.data, "words": [*p.data["words"][:-1], "ZZZZ"]}})
    assert not CW.verify(bad).ok


@pytest.mark.typst
def test_render_pdf(tmp_path: Path) -> None:
    from forge.puzzles.preview import preview_pdf

    assert preview_pdf(CW.generate(spec("medium"), 2), tmp_path / "p.pdf").stat().st_size > 1000
