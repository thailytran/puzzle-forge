from __future__ import annotations

from pathlib import Path
from statistics import mean

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import LEVELS, PuzzleSpec
from forge.core.protocol import PuzzleType, RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.wordsearch import WordSearch
from forge.puzzles.wordsearch.params import BACKWARD
from forge.wordlists import available_themes

WS = WordSearch()
CTX = RenderCtx(width_in=7.0, height_in=9.5)
THEMES = [t for t in available_themes() if t != "short_words"]


def spec(level: str = "easy", audience: str = "adult", **kw: object) -> PuzzleSpec:
    data: dict[str, object] = {"type": "wordsearch", "level": level, "audience": audience}
    data.setdefault("theme", "ocean")
    data.update(kw)
    return PuzzleSpec.model_validate(data)


def test_is_puzzle_type() -> None:
    assert isinstance(WS, PuzzleType)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=0, max_value=2**32),
    level=st.sampled_from(LEVELS),
    audience=st.sampled_from(["kids_6_8", "kids_9_12", "adult", "senior_large_print"]),
    theme=st.sampled_from(THEMES),
)
def test_every_generated_puzzle_verifies(seed: int, level: str, audience: str, theme: str) -> None:
    p = WS.generate(spec(level, audience, theme=theme), seed)
    report = WS.verify(p)
    assert report.ok, report.messages
    assert report.unique
    assert p.verify is not None and p.verify.ok
    assert p.difficulty is not None
    if audience == "kids_6_8":
        assert not any(pl["dir"] in BACKWARD for pl in p.solution["placements"])


def test_deterministic() -> None:
    a = WS.generate(spec("hard"), 123)
    b = WS.generate(spec("hard"), 123)
    assert a.model_dump_json() == b.model_dump_json()


def test_seed_changes_puzzle() -> None:
    assert WS.generate(spec(), 1).content_hash != WS.generate(spec(), 2).content_hash


def test_explicit_words() -> None:
    words = ["apple", "banana", "cherry", "grape", "lemon", "mango", "peach"]
    p = WS.generate(spec("very_easy", words=words, theme=None), 5)
    assert set(p.data["words"]) <= {w.upper() for w in words}
    assert len(p.data["words"]) >= 6


def test_too_few_words() -> None:
    with pytest.raises(GenerationError):
        WS.generate(spec(words=["ox", "cat"], theme=None), 1)


@pytest.mark.parametrize("message", ["HARBOR", "THE KEY IS UNDER THE MAT", "LOOK NORTH"])
@pytest.mark.parametrize("level", ["easy", "medium", "hard"])
def test_hidden_message(message: str, level: str) -> None:
    s = spec(level, constraints=[{"kind": "hidden_message", "text": message}])
    p = WS.generate(s, 7)
    target = message.replace(" ", "")
    assert p.token == target
    solved = WS.solve(p).solution
    assert solved is not None
    assert solved["leftover"] == target


def test_hidden_message_impossible() -> None:
    s = spec("very_easy", constraints=[{"kind": "hidden_message", "text": "A" * 300}])
    with pytest.raises(GenerationError):
        WS.generate(s, 1)


@pytest.mark.parametrize("shape", ["circle", "diamond"])
def test_masks(shape: str) -> None:
    p = WS.generate(spec("medium", options={"shape": shape}), 3)
    assert any("." in row for row in p.data["rows"])
    assert WS.verify(p).ok


def test_verify_detects_duplicate_word() -> None:
    p = WS.generate(spec("easy"), 9)
    word = p.data["words"][0]
    rows = list(p.data["rows"])
    # overwrite the start of a row that does not contain the word with a second copy
    for i, row in enumerate(rows):
        if len(word) <= len(row) and not any((pl["row"] == i) for pl in p.solution["placements"]):
            rows[i] = word + row[len(word) :]
            break
    else:
        pytest.skip("no free row")
    bad = p.model_copy(update={"data": {**p.data, "rows": rows}})
    rep = WS.verify(bad)
    assert not rep.ok


def test_verify_detects_missing_word() -> None:
    p = WS.generate(spec("easy"), 9)
    bad = p.model_copy(update={"data": {**p.data, "words": [*p.data["words"], "ZZZZQ"]}})
    assert not WS.verify(bad).ok


def test_difficulty_increases_with_level() -> None:
    avg = {
        lvl: mean(
            WS.generate(spec(lvl, theme=t), s).difficulty.score  # type: ignore[union-attr]
            for s in range(2)
            for t in ("ocean", "space")
        )
        for lvl in LEVELS
    }
    assert avg["very_easy"] < avg["easy"] < avg["medium"] < avg["hard"] < avg["expert"]


@pytest.mark.parametrize("level", ["very_easy", "easy", "hard", "expert"])
def test_adult_label_matches_level(level: str) -> None:
    p = WS.generate(spec(level), 4)
    assert p.difficulty is not None
    assert p.difficulty.label == level


def test_render_blocks() -> None:
    p = WS.generate(spec("medium"), 2)
    blocks = WS.render(p, CTX).blocks
    grid = next(b for b in blocks if b["kind"] == "letter_grid")
    assert len(grid["rows"]) == len(p.data["rows"])
    wl = next(b for b in blocks if b["kind"] == "word_list")
    assert {w for w in wl["words"] if w} == set(p.data["words"])
    sol = WS.render_solution(p, CTX).blocks[0]
    assert len(sol["highlights"]) == len(p.data["words"])


def test_kids_cells_big_enough() -> None:
    p = WS.generate(spec("easy", "kids_6_8"), 2)
    grid = WS.render(p, CTX).blocks[0]
    assert grid["cell_in"] >= 0.45


@pytest.mark.typst
def test_render_pdf(tmp_path: Path) -> None:
    from forge.puzzles.preview import preview_pdf

    p = WS.generate(spec("hard", options={"shape": "circle"}), 2)
    pdf = preview_pdf(p, tmp_path / "preview.pdf", trim="8.5x11")
    assert pdf.stat().st_size > 1000
