from __future__ import annotations

import itertools
import json
from collections import Counter
from pathlib import Path

import pytest

from forge.book.builder import build_book, layout_book, verify_book
from forge.book.plan import plan_book
from forge.core.book import BookSpec, load_book_spec

ROOT = Path(__file__).resolve().parents[1]


def small(mode: str = "mixed", pages: int = 12) -> BookSpec:
    return BookSpec.model_validate(
        {
            "book": {
                "title": "Test Book",
                "audience": "adult",
                "trim": "8.5x11",
                "content_pages": pages,
                "seed": 7,
            },
            "puzzles": {
                "mode": mode,
                "distribution": {"easy": 1, "medium": 1, "hard": 1},
                "types": [
                    {"type": "wordsearch", "weight": 2},
                    {"type": "sudoku"},
                    {"type": "maze"},
                ],
            },
            "solutions": {"per_page": 6},
        }
    )


def test_plan_counts_and_weights() -> None:
    slots = plan_book(small(pages=40))
    assert len(slots) == 40
    c = Counter(s.type for s in slots)
    assert c["wordsearch"] == 20 and c["sudoku"] == 10 and c["maze"] == 10
    assert all(s.theme for s in slots if s.type == "wordsearch")
    assert all(s.theme is None for s in slots if s.type == "sudoku")


def test_progressive_levels_non_decreasing() -> None:
    order = ["very_easy", "easy", "medium", "hard", "expert"]
    lv = [order.index(s.level) for s in plan_book(small("progressive", 30))]
    assert lv == sorted(lv)


def test_mixed_sections_each_have_all_levels() -> None:
    slots = plan_book(small("mixed", 30))
    for k in range(0, 30, 10):
        assert {s.level for s in slots[k : k + 10]} == {"easy", "medium", "hard"}


def test_by_section_groups_types() -> None:
    types = [s.type for s in plan_book(small("by_section", 20))]
    changes = sum(a != b for a, b in itertools.pairwise(types))
    assert changes == 2


def test_example_specs_plan() -> None:
    for name in ("example_wordsearch", "example_mixed", "example_sudoku_large_print"):
        spec = load_book_spec(ROOT / f"configs/books/{name}.yaml")
        assert len(plan_book(spec)) == spec.book.content_pages


def test_build_no_render(tmp_path: Path) -> None:
    out = build_book(small(), tmp_path / "out", tmp_path / "f.db", render=False)
    man = json.loads((out / "manifest.json").read_text())
    assert len(man["puzzles"]) == 12
    assert man["page_count"] % 2 == 0
    assert all(p["verify"]["ok"] for p in man["puzzles"])
    assert all(p["solution_page"] > p["page"] for p in man["puzzles"])
    # rebuilding the same book is idempotent (registry accepts its own puzzles)
    out2 = build_book(small(), tmp_path / "out", tmp_path / "f.db", render=False)
    assert (out2 / "manifest.json").read_text() == (out / "manifest.json").read_text()


def test_toc_points_at_real_pages(tmp_path: Path) -> None:
    from forge.book.builder import generate_puzzles
    from forge.core.registry import Registry

    spec = small()
    with Registry(tmp_path / "f.db") as reg:
        pz = generate_puzzles(spec, "b", reg)
    built = layout_book(spec, pz)
    pages = built.doc.pages
    toc = next(p for p in pages if p.title == "Contents").blocks[0]["entries"]
    for e in toc:
        target = pages[e["page"] - 1]
        if e["title"] == "Puzzles":
            assert target.kind == "puzzle"
        elif e["title"] == "Solutions":
            assert target.kind == "solutions"
        else:
            assert target.title == e["title"]


@pytest.mark.typst
def test_build_and_verify_pdf(tmp_path: Path) -> None:
    spec = BookSpec.model_validate(
        {
            **small().model_dump(mode="json"),
            "puzzles": {
                "mode": "mixed",
                "types": [
                    {"type": t}
                    for t in ("wordsearch", "sudoku", "maze", "scramble", "cryptogram", "crossword")
                ],
            },
        }
    )
    out = build_book(spec, tmp_path / "out", tmp_path / "f.db")
    assert verify_book(out) == []
    from pypdf import PdfReader

    man = json.loads((out / "manifest.json").read_text())
    assert len(PdfReader(out / "interior.pdf").pages) == man["page_count"]
