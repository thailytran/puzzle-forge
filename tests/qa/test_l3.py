from __future__ import annotations

import copy
from pathlib import Path

import pytest

from forge.book.builder import build_book
from forge.core.book import BookSpec
from forge.qa.checks import REGISTRY, run_one
from forge.qa.gate import BookContext, load_check_modules
from forge.qa.l2 import layout, pdf

pytestmark = pytest.mark.typst


@pytest.fixture(scope="module")
def book(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("l3")
    spec = BookSpec.model_validate(
        {
            "book": {"title": "L3 Book", "audience": "adult", "content_pages": 12, "seed": 5},
            "puzzles": {
                "mode": "mixed",
                "types": [{"type": "wordsearch"}, {"type": "sudoku"}, {"type": "crossword"}],
            },
        }
    )
    out = build_book(spec, tmp / "o", tmp / "f.db")
    load_check_modules()
    return out, tmp / "f.db"


def ctx(book: tuple[Path, Path]) -> BookContext:
    return BookContext(*book)


@pytest.mark.parametrize(
    "cid",
    ["L3.counts", "L3.distribution", "L3.toc", "L3.matter", "L3.proofread", "L3.placeholders"],
)
def test_l3_pass(book: tuple[Path, Path], cid: str) -> None:
    r = run_one(REGISTRY[cid], ctx(book))
    assert r.status == "pass", [f.message for f in r.findings]


def _edit_layout(c: BookContext, fn) -> None:  # type: ignore[no-untyped-def]
    lay = copy.deepcopy(layout(c))
    fn(lay)
    c.extra["layout"] = lay


def test_counts_detect_missing_puzzles(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    c.__dict__["manifest"] = {**c.manifest, "puzzles": c.manifest["puzzles"][:-1]}
    assert run_one(REGISTRY["L3.counts"], c).status == "fail"


def test_distribution_detects_swapped_type(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    rows = [dict(r) for r in c.manifest["puzzles"]]
    rows[0]["type"] = "maze"
    c.__dict__["manifest"] = {**c.manifest, "puzzles": rows}
    assert run_one(REGISTRY["L3.distribution"], c).status == "fail"


def test_toc_detects_wrong_page(book: tuple[Path, Path]) -> None:
    c = ctx(book)

    def bump(lay: dict) -> None:  # type: ignore[type-arg]
        page = next(p for p in lay["pages"] if p.get("title") == "Contents")
        page["blocks"][0]["entries"][-1]["page"] += 1

    _edit_layout(c, bump)
    assert run_one(REGISTRY["L3.toc"], c).status == "fail"


def test_matter_detects_missing_copyright(book: tuple[Path, Path]) -> None:
    c = ctx(book)
    facts = pdf(c)
    pages = []
    for p in facts.pages:
        q = copy.copy(p)
        q.text = p.text.replace("Copyright", "")
        pages.append(q)
    facts.__dict__["pages"] = pages
    assert run_one(REGISTRY["L3.matter"], c).status == "fail"


def test_proofread_detects_typo(book: tuple[Path, Path]) -> None:
    c = ctx(book)

    def typo(lay: dict) -> None:  # type: ignore[type-arg]
        page = next(p for p in lay["pages"] if p.get("title") == "How to Play")
        page["blocks"].append({"kind": "paragraph", "text": "Find the the wrods quickly."})

    _edit_layout(c, typo)
    r = run_one(REGISTRY["L3.proofread"], c)
    msgs = " ".join(f.message for f in r.findings)
    assert r.status == "fail" and "wrods" in msgs and "repeated" in msgs


@pytest.mark.parametrize(
    "text", ["TODO add rules", "Hello {name}", "Lorem ipsum", "Dear <pen_name>"]
)
def test_placeholders_detected(book: tuple[Path, Path], text: str) -> None:
    c = ctx(book)
    _edit_layout(
        c, lambda lay: lay["pages"][2]["blocks"].append({"kind": "paragraph", "text": text})
    )
    assert run_one(REGISTRY["L3.placeholders"], c).status == "fail"
