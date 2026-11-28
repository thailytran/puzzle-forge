from __future__ import annotations

from pathlib import Path

import pytest

from forge.core.models import PuzzleSpec, build_puzzle
from forge.core.registry import DuplicatePuzzleError, Registry


def _p(n: int, type_: str = "sudoku"):  # type: ignore[no-untyped-def]
    spec = PuzzleSpec(type=type_, level="easy", audience="adult")
    return build_puzzle(spec, seed=n, data={"n": n}, solution={})


@pytest.fixture
def reg(tmp_path: Path):  # type: ignore[no-untyped-def]
    with Registry(tmp_path / "sub" / "forge.db") as r:
        yield r


def test_add_and_contains(reg: Registry) -> None:
    p = _p(1)
    reg.add(p, book_id="b1")
    assert reg.contains(p.content_hash)
    assert not reg.contains(_p(2).content_hash)


def test_duplicate_across_books_rejected(reg: Registry) -> None:
    reg.add(_p(1), book_id="b1")
    with pytest.raises(DuplicatePuzzleError) as e:
        reg.add(_p(1), book_id="b2")
    assert e.value.existing_book == "b1"


def test_readd_same_book_is_idempotent(reg: Registry) -> None:
    reg.add(_p(1), book_id="b1")
    reg.add(_p(1), book_id="b1")
    assert len(reg.list_by_book("b1")) == 1


def test_try_add(reg: Registry) -> None:
    assert reg.try_add(_p(1), book_id="b1")
    assert not reg.try_add(_p(1), book_id="b2")


def test_list_by_book_ordered(reg: Registry) -> None:
    for n in (3, 1, 2):
        reg.add(_p(n), book_id="b1")
    reg.add(_p(9), book_id="b2")
    entries = reg.list_by_book("b1")
    assert [e.seed for e in entries] == [3, 1, 2]
    assert all(e.book_id == "b1" for e in entries)
    assert entries[0].type == "sudoku"


def test_remove_book(reg: Registry) -> None:
    reg.add(_p(1), book_id="b1")
    assert reg.remove_book("b1") == 1
    assert reg.try_add(_p(1), book_id="b2")


def test_stats(reg: Registry) -> None:
    reg.add(_p(1), book_id="b1")
    reg.add(_p(2, "maze"), book_id="b1")
    reg.add(_p(3, "maze"), book_id="b2")
    assert reg.stats() == {"maze": 2, "sudoku": 1}
    assert reg.books() == ["b1", "b2"]


def test_persists(tmp_path: Path) -> None:
    db = tmp_path / "f.db"
    with Registry(db) as r:
        r.add(_p(1), book_id="b1")
    with Registry(db) as r:
        assert r.contains(_p(1).content_hash)
