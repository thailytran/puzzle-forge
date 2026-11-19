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
    simulate_reader,
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
        d["chapters"][0]["object"] = "owl"  # no picture
        d["chapters"][2]["side"][1]["keyword"] = "two words"
        d["chapters"][3]["story"] = "A murder at the river."
        d["chapters"][5]["shape"] = "blob"
        d["chapters"][6]["shape"] = "triangle"  # a 13 x 13 picture needs smaller cells than 5 mm

    probs = check_frame(edited(frame, bad), deep=False).problems
    for needle in (
        "object 'owl'",
        "one word",
        "family-friendly",
        "unknown cell shape",
        "does not fit",
    ):
        assert any(needle in p for p in probs), (needle, probs)


def problems(frame: CaseFrame, fn: object) -> list[str]:
    return check_frame(edited(frame, fn), deep=False).problems


def test_logic_lock_rejects_unfair_cases(frame: CaseFrame) -> None:
    def strong(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["clue"] = {"field": "name", "op": "eq", "value": d["answer"]}

    assert any("too strong" in p for p in problems(frame, strong))

    def hits_culprit(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][2]["clue"] = {"field": "boots", "op": "eq", "value": False}

    assert any("crosses out the culprit" in p for p in problems(frame, hits_culprit))

    def live_decoy(d: dict) -> None:  # type: ignore[type-arg]  # wrong row -> a wrong culprit
        d["chapters"][0]["decoys"][0]["clue"] = {"field": "scarf", "op": "eq", "value": "green"}

    assert any("must be a dead end" in p for p in problems(frame, live_decoy))

    def same_as_true(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["decoys"][0]["clue"] = d["chapters"][0]["clue"]

    assert any("says the same" in p for p in problems(frame, same_as_true))


def test_card_needs_all_three_answers(frame: CaseFrame) -> None:
    def no_object_decoy(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["decoys"].pop(0)

    assert any("another object" in p for p in problems(frame, no_object_decoy))

    def no_keyword_decoy(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["decoys"].pop(1)

    assert any("only WOOLLEN differs" in p for p in problems(frame, no_keyword_decoy))


def test_story_may_not_give_the_answer_away(frame: CaseFrame) -> None:
    def leak(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["story"] += " It was a crimson scarf."

    probs = problems(frame, leak)
    assert any("gives away the answer SCARF" in p for p in probs)
    assert any("gives away the answer CRIMSON" in p for p in probs)


def test_causal_graph() -> None:
    from forge.mystery.causal_graph import CausalGraph

    g = CausalGraph()
    g.add("p1", "puzzle")
    g.add("p2", "puzzle")
    g.add("orphan", "puzzle")
    g.add("card", "evidence", ("p1", "p2"))
    g.add("final", "final", ("card",))
    assert g.problems() == ["orphan is not needed for the final answer"]
    assert g.closure("final") == {"card", "p1", "p2"}
    bad = CausalGraph()
    bad.add("card", "evidence", ("p9",))
    bad.add("final", "final", ("card",))
    assert any("unknown node" in p for p in bad.problems())


def test_reader_simulation(frame: CaseFrame) -> None:
    built = build_puzzles(frame, 7)
    run = simulate_reader(frame, built)
    assert run.ok, run.problems
    assert run.left_after == [10, 9, 7, 5, 4, 3, 2, 1] and run.answer == [frame.answer]

    def swap(d: dict) -> None:  # type: ignore[type-arg]  # card no longer matches the puzzles
        d["chapters"][3]["side"][1]["keyword"] = "OPEN"

    assert not simulate_reader(edited(frame, swap), built).ok


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
        assert cb.solve(cp.cbn).solution["code"] == code_of(ch)
        assert cp.cbn.data["shape"] == ch.shape
        assert cb.verify(cp.cbn).ok
    again = build_puzzles(frame, 7)
    assert [b.cbn.content_hash for b in built] == [b.cbn.content_hash for b in again]
    assert {b.cbn.data["shape"] for b in built} == {"square", "hex"}


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
    assert len(rows) == 4  # the true row + one decoy per answer (picture, keyword 1, keyword 2)
    assert sum("SCARF" in r for r in rows) == 3 and sum("WOOLLEN" in r for r in rows) == 3


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


def test_number_games_and_case_words(frame: CaseFrame) -> None:
    from forge.mystery.cbn_case import side_spec

    assert len(frame.suspects) == 12
    types = [sp.type for ch in frame.chapters for sp in ch.side]
    assert types.count("numlock") == 2
    built = build_puzzles(frame, 7)
    assert built[2].side[0].token == "44" and built[5].side[1].token == "1200"
    ws = side_spec(frame, frame.chapters[0].side[1], 0)
    assert ws.words and "LARKSPUR" in ws.words
    secret = {ch.object.upper() for ch in frame.chapters}
    secret |= {sp.keyword.upper() for ch in frame.chapters for sp in ch.side}
    assert not secret & set(ws.words)  # filler words never contain an answer of the case

    def few(d: dict) -> None:  # type: ignore[type-arg]
        d["suspects"] = d["suspects"][:8]

    assert any("9-12 suspects" in p for p in problems(frame, few))

    def word_for_lock(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][2]["side"][0]["keyword"] = "HEAVY"

    assert any("2-4 digits" in p for p in problems(frame, word_for_lock))


def test_sudoku_side_puzzle_spec(frame: CaseFrame) -> None:
    from forge.mystery.cbn_case import SidePuzzle, side_spec

    sp = SidePuzzle(type="sudoku", keyword="47")
    spec = side_spec(frame, sp, 3)
    assert spec.options["size"] == 9 and spec.constraints[0].expect == "47"  # type: ignore[union-attr]
    pytest.importorskip("rustoku")
    from forge.puzzles.sudoku import Sudoku

    pz = Sudoku().generate(spec, 5)
    assert pz.token == "47" and Sudoku().verify(pz).ok
