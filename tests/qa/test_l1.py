from __future__ import annotations

from pathlib import Path

import pytest

from forge.book.builder import build_book
from forge.book.plan import cap_level, plan_book
from forge.core.book import BookSpec
from forge.qa.checks import REGISTRY, run_one
from forge.qa.gate import BookContext, load_check_modules
from forge.qa.l1 import band_ok
from forge.qa.solvers2 import SOLVERS, matches_stored


def spec(audience: str = "adult", types: tuple[str, ...] = ("wordsearch", "sudoku")) -> BookSpec:
    return BookSpec.model_validate(
        {
            "book": {"title": "QA Book", "audience": audience, "content_pages": 8, "seed": 3},
            "puzzles": {"mode": "mixed", "types": [{"type": t} for t in types]},
        }
    )


@pytest.fixture
def built(tmp_path: Path) -> BookContext:
    s = spec(types=("wordsearch", "sudoku", "maze", "scramble", "cryptogram", "crossword"))
    out = build_book(s, tmp_path / "o", tmp_path / "f.db", render=False)
    load_check_modules()
    return BookContext(out, tmp_path / "f.db")


def test_band_rules() -> None:
    assert band_ok("hard", "hard", "adult")
    assert not band_ok("hard", "medium", "adult")
    assert band_ok("easy", "very_easy", "kids_6_8")
    assert not band_ok("hard", "easy", "kids_9_12")


def test_caps() -> None:
    assert cap_level("expert", "scramble", "adult") == "hard"
    assert cap_level("hard", "sudoku", "kids_6_8") == "medium"
    assert cap_level("hard", "crossword", "senior_large_print") == "medium"
    assert cap_level("medium", "maze", "adult") == "medium"
    slots = plan_book(spec("kids_6_8"))
    assert all(s.level in ("very_easy", "easy", "medium") for s in slots)
    assert any(s.requested_level for s in slots)


def test_second_solvers_agree(built: BookContext) -> None:
    for p in built.puzzles:
        count, sol = SOLVERS[p.type](p)
        assert count == 1, p.id
        assert matches_stored(p, sol), p.id


@pytest.mark.parametrize(
    "cid", ["L1.dual_solver", "L1.unique", "L1.rules", "L1.difficulty_band", "L1.catalog_unique"]
)
def test_l1_checks_pass_on_good_book(built: BookContext, cid: str) -> None:
    r = run_one(REGISTRY[cid], built)
    assert r.status == "pass", r.findings


def test_l1_detects_tampering(built: BookContext) -> None:
    p = next(x for x in built.puzzles if x.type == "sudoku")
    givens = [list(r) for r in p.data["givens"]]
    givens[0] = [0] * len(givens[0])
    givens[1] = [0] * len(givens[1])
    bad = p.model_copy(update={"data": {**p.data, "givens": givens}})
    built.__dict__["puzzles"] = [bad if x is p else x for x in built.puzzles]
    assert run_one(REGISTRY["L1.dual_solver"], built).status == "fail"


def test_catalog_duplicate_detected(built: BookContext, tmp_path: Path) -> None:
    from forge.core.registry import Registry

    p = built.puzzles[0]
    with Registry(built.db_path) as reg:
        reg.remove_book(built.book_id)
        reg.add(p, "some-other-book")
    r = run_one(REGISTRY["L1.catalog_unique"], built)
    assert r.status == "fail"
    assert any("some-other-book" in f.message for f in r.findings)


def test_kid_safety_skips_adult_and_runs_for_kids(tmp_path: Path) -> None:
    out = build_book(spec("kids_6_8"), tmp_path / "o", tmp_path / "f.db", render=False)
    load_check_modules()
    ctx = BookContext(out, tmp_path / "f.db")
    assert run_one(REGISTRY["L1.kid_safety"], ctx).status == "pass"
    out2 = build_book(spec(), tmp_path / "o2", tmp_path / "g.db", render=False)
    assert run_one(REGISTRY["L1.kid_safety"], BookContext(out2, tmp_path / "g.db")).status == "skip"
