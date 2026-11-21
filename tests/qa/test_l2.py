from __future__ import annotations

import copy
from pathlib import Path

import pytest

from forge.book.builder import build_book
from forge.core.book import BookSpec
from forge.qa.checks import REGISTRY, run_one
from forge.qa.gate import BookContext, load_check_modules, run_gate
from forge.qa.l2 import pdf

pytestmark = pytest.mark.typst


@pytest.fixture(scope="module")
def book(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("l2")
    spec = BookSpec.model_validate(
        {
            "book": {
                "title": "L2 Book",
                "audience": "senior_large_print",
                "large_print": True,
                "content_pages": 6,
                "seed": 11,
            },
            "puzzles": {
                "mode": "mixed",
                "types": [
                    {"type": t}
                    for t in ("wordsearch", "sudoku", "maze", "cryptogram", "scramble", "crossword")
                ],
            },
            "solutions": {"per_page": 4},
        }
    )
    out = build_book(spec, tmp / "o", tmp / "f.db")
    load_check_modules()
    return out, tmp / "f.db"


def ctx(book: tuple[Path, Path]) -> BookContext:
    return BookContext(*book)


def test_gate_passes_l1_l2(book: tuple[Path, Path]) -> None:
    r = run_gate(book[0], book[1], layers={"L1", "L2"})
    failed = [(c.id, c.message) for c in r.checks if c.status == "fail"]
    assert r.result == "PASSED", failed
    assert (book[0] / "previews" / "page-001.png").is_file()


def test_trim_mismatch_detected(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    c.__dict__["manifest"] = {**c.manifest, "trim": "6x9"}
    assert run_one(REGISTRY["L2.trim"], c).status == "fail"


def test_ink_outside_margin_detected(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    facts = pdf(c)
    page = copy.copy(facts.pages[4])
    page.ink_box = (2, 100, 300, 500)
    facts.__dict__["pages"] = [*facts.pages[:4], page, *facts.pages[5:]]
    r = run_one(REGISTRY["L2.safe_area"], c)
    assert r.status == "fail" and r.findings[0].evidence["page"] == 5


def test_small_text_detected(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    facts = pdf(c)
    page = copy.copy(facts.pages[4])
    page.chars = [*page.chars, ("x", 9.0, 100.0, 300.0)]
    facts.__dict__["pages"] = [*facts.pages[:4], page, *facts.pages[5:]]
    assert run_one(REGISTRY["L2.min_sizes"], c).status == "fail"


def test_blank_page_detected(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    facts = pdf(c)
    page = copy.copy(facts.pages[4])
    page.body_ink = False
    facts.__dict__["pages"] = [*facts.pages[:4], page, *facts.pages[5:]]
    assert run_one(REGISTRY["L2.no_unintended_blank"], c).status == "fail"


def test_roundtrip_detects_changed_puzzle(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    ws = next(p for p in c.puzzles if p.type == "wordsearch")
    rows = list(ws.data["rows"])
    rows[0] = ("Q" if rows[0][0] != "Q" else "Z") + rows[0][1:]
    bad = ws.model_copy(update={"data": {**ws.data, "rows": rows}})
    c.__dict__["puzzles"] = [bad if p is ws else p for p in c.puzzles]
    r = run_one(REGISTRY["L1.print_roundtrip"], c)
    assert r.status == "fail" and r.findings[0].evidence["puzzle_id"] == ws.id


def test_solution_pointer_detected(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    rows = [dict(r) for r in c.manifest["puzzles"]]
    rows[0]["page"] = rows[1]["page"]
    c.__dict__["manifest"] = {**c.manifest, "puzzles": rows}
    assert run_one(REGISTRY["L2.solution_match"], c).status == "fail"


def test_overflow_detected(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    lay = pdf(c) and __import__("forge.qa.l2", fromlist=["layout"]).layout(c)
    c.extra["layout"] = {**lay, "pages": [*lay["pages"], lay["pages"][-1]]}
    assert run_one(REGISTRY["L2.page_count_match"], c).status == "fail"
