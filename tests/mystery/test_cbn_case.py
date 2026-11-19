from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.blueprints import load_blueprint, validate_blueprint
from forge.core.protocol import RenderCtx
from forge.mystery.cbn_case import (
    CaseFrame,
    build_case_book,
    build_puzzles,
    check_frame,
    code_of,
    layout_pages,
    load_frame,
)
from forge.mystery.necessity import CaseError
from forge.puzzles.cbn import ColorByNumber

CASE = Path(__file__).resolve().parents[2] / "configs" / "cases" / "vanished_star.json"


@pytest.fixture(scope="module")
def frame() -> CaseFrame:
    return load_frame(CASE)


def edited(frame: CaseFrame, fn: object) -> CaseFrame:
    data = json.loads(frame.model_dump_json())
    fn(data)  # type: ignore[operator]
    return CaseFrame.model_validate(data)


def test_sample_frame_is_accepted(frame: CaseFrame) -> None:
    rep = check_frame(frame)
    assert rep.ok, rep.problems
    assert rep.necessity["solutions"] == [frame.answer]


def test_blueprint_matches_spec() -> None:
    bp = load_blueprint("cbn_mystery")
    assert validate_blueprint(bp) == []
    assert bp.chapter == ["story", "cbn_reveal", "side_puzzle", "side_puzzle", "evidence_card"]
    assert 8 * len(bp.chapter) == 40 and 8 * 3 == 24  # 8 chapters: 40 pages, 24 puzzle pages


def test_redundant_clue_is_rejected(frame: CaseFrame) -> None:
    def dup(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][1]["clue"] = d["chapters"][0]["clue"]

    rep = check_frame(edited(frame, dup), deep=False)
    assert not rep.ok and any("not needed" in p or "candidates" in p for p in rep.problems)


def test_wrong_answer_and_bad_inputs(frame: CaseFrame) -> None:
    def wrong(d: dict) -> None:  # type: ignore[type-arg]
        d["answer"] = d["suspects"][1]["name"]

    assert any(
        "declared answer" in p for p in check_frame(edited(frame, wrong), deep=False).problems
    )

    def bad(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["symbol"] = "OWL"  # too long
        d["chapters"][2]["side"][0]["keyword"] = "two words"
        d["chapters"][3]["story"] = "A murder at the bridge."
        d["chapters"][5]["symbol"] = "0"
        d["chapters"][5]["shape"] = "blob"

    probs = check_frame(edited(frame, bad), deep=False).problems
    for needle in ("symbol 'OWL'", "one word", "family-friendly", "unknown cell shape"):
        assert any(needle in p for p in probs), (needle, probs)


def test_unbuildable_keyword_is_caught(frame: CaseFrame) -> None:
    def kw(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["side"][0]["keyword"] = "MITTEN"  # has another anagram

    probs = check_frame(edited(frame, kw)).problems
    assert any("cannot produce keyword MITTEN" in p for p in probs)


def test_puzzles_carry_the_locked_answers(frame: CaseFrame) -> None:
    cb = ColorByNumber()
    built = build_puzzles(frame, 7)
    assert len(built) == 8 and sum(1 + len(b.side) for b in built) == 24
    for ch, cp in zip(frame.chapters, built, strict=True):
        assert cb.solve(cp.cbn).solution["code"] == code_of(ch.symbol)
        assert cp.cbn.data["shape"] == ch.shape
        assert cb.verify(cp.cbn).ok
    again = build_puzzles(frame, 7)
    assert [b.cbn.content_hash for b in built] == [b.cbn.content_hash for b in again]
    assert {b.cbn.data["shape"] for b in built} == {"square", "hex", "triangle"}


def test_layout_has_five_pages_per_chapter(frame: CaseFrame) -> None:
    pages, _files, art = layout_pages(frame, build_puzzles(frame, 7), RenderCtx(7.0, 9.0))
    titles = [p.title or "" for p in pages]
    for n in range(1, 9):
        assert sum(t.startswith(f"Chapter {n}:") for t in titles) == 4
        assert f"Evidence Card {n}" in titles
    assert sum(p.kind == "puzzle" for p in pages) == 24
    assert len(art) >= 8 and all(a["brief"] for a in art)
    card = next(p for p in pages if p.title == "Evidence Card 1")
    rows = next(b for b in card.blocks if b["kind"] == "list")["items"]
    assert len(rows) == 3  # the true reading and two decoys: the mosaic decides


def test_manifest_without_render(frame: CaseFrame, tmp_path: Path) -> None:
    man = build_case_book(frame, tmp_path, render=False)
    assert man["puzzle_pages"] == 24 and man["frame_check"]["ok"]
    assert frame.answer not in (tmp_path / "manifest.json").read_text(encoding="utf-8")


def test_rejected_frame_does_not_build(frame: CaseFrame, tmp_path: Path) -> None:
    def wrong(d: dict) -> None:  # type: ignore[type-arg]
        d["answer"] = d["suspects"][1]["name"]

    with pytest.raises(CaseError):
        build_case_book(edited(frame, wrong), tmp_path, render=False)


@pytest.mark.typst
def test_book_renders(frame: CaseFrame, tmp_path: Path) -> None:
    build_case_book(frame, tmp_path)
    assert (tmp_path / "interior.pdf").stat().st_size > 50_000
