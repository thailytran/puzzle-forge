from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from forge.core.book import BookSpec, load_book_spec

ROOT = Path(__file__).resolve().parents[2]


def test_load_example() -> None:
    spec = load_book_spec(ROOT / "configs/books/example_wordsearch.yaml")
    assert spec.book.title == "Ocean Adventures Word Search"
    assert spec.book.trim == "8.5x11"
    assert spec.puzzles.mode == "progressive"
    assert spec.puzzles.types[0].type == "wordsearch"
    assert spec.solutions.per_page == 6
    assert spec.puzzles.level_counts(spec.book.content_pages) == {
        "easy": 30,
        "medium": 40,
        "hard": 30,
    }


def _minimal(**puzzles: object) -> dict[str, object]:
    p: dict[str, object] = {"types": [{"type": "sudoku"}]}
    p.update(puzzles)
    return {
        "book": {"title": "T", "audience": "adult", "trim": "6x9", "content_pages": 10, "seed": 1},
        "puzzles": p,
    }


def test_level_counts_sum_to_pages() -> None:
    spec = BookSpec.model_validate(_minimal(distribution={"easy": 1, "medium": 1, "hard": 1}))
    counts = spec.puzzles.level_counts(10)
    assert sum(counts.values()) == 10
    assert counts == {"easy": 4, "medium": 3, "hard": 3}


def test_bad_trim_rejected() -> None:
    data = _minimal()
    data["book"]["trim"] = "5x5"  # type: ignore[index]
    with pytest.raises(ValidationError):
        BookSpec.model_validate(data)


def test_empty_types_rejected() -> None:
    with pytest.raises(ValidationError):
        BookSpec.model_validate(_minimal(types=[]))


def test_unknown_field_rejected() -> None:
    data = _minimal()
    data["bogus"] = 1
    with pytest.raises(ValidationError):
        BookSpec.model_validate(data)


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_book_spec(tmp_path / "nope.yaml")
