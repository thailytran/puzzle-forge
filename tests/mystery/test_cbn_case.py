from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.blueprints import load_blueprint, validate_blueprint
from forge.core.protocol import RenderCtx
from forge.mystery.cbn_case import (
    SIDE_TYPES,
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
        d["chapters"][6]["shape"] = "triangle"  # drawn pictures bring their own square grid

    probs = check_frame(edited(frame, bad), deep=False).problems
    for needle in (
        "object 'owl'",
        "one word",
        "family-friendly",
        "unknown cell shape",
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


def test_only_code_puzzles_are_allowed(frame: CaseFrame) -> None:
    """Owner rule: no filler puzzles. Word scramble / word search are not side puzzles any more,
    and a shift cipher must decode a sentence of the case that holds the keyword."""
    import pydantic

    def ws(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["side"][0]["type"] = "wordsearch"

    with pytest.raises(pydantic.ValidationError):
        edited(frame, ws)

    def no_message(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][0]["side"][0]["message"] = "The answer is here"

    assert any("cipher needs a message" in p for p in problems(frame, no_message))


def test_puzzles_carry_the_locked_answers(frame: CaseFrame) -> None:
    cb = ColorByNumber()
    built = build_puzzles(frame, 7)
    assert len(built) == 8 and sum(1 + len(b.side) for b in built) == 24
    for ch, cp in zip(frame.chapters, built, strict=True):
        assert cb.solve(cp.cbn).solution["code"] == code_of(ch)
        want = ch.shape if ch.shape in ("square", "circle") else "square"  # picture lattice
        assert cp.cbn.data["shape"] == want and cp.cbn.data["art"] is True
        assert cb.verify(cp.cbn).ok
    again = build_puzzles(frame, 7)
    assert [b.cbn.content_hash for b in built] == [b.cbn.content_hash for b in again]
    assert {b.cbn.data["shape"] for b in built} <= {"square", "circle"}


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


def test_number_games(frame: CaseFrame) -> None:
    assert len(frame.suspects) == 12
    types = [sp.type for ch in frame.chapters for sp in ch.side]
    assert types.count("numlock") == 2 and set(types) <= set(SIDE_TYPES)
    # owner 2026-11-21: the sample book carries the new logic games too
    assert {"wordoku", "starbattle", "wordladder", "pigpen", "lightup"} <= set(types)
    built = build_puzzles(frame, 7)
    assert built[2].side[0].token == "44" and built[5].side[1].token == "1200"
    note = built[0].side[0].solution["plain"]
    assert "WOOLLEN" in note and note.startswith("THE WEAVER")

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


def test_story_never_spoils_what_is_found_later(frame: CaseFrame) -> None:
    def early(d: dict) -> None:  # type: ignore[type-arg]
        d["prologue"] += " A ladder leaned on the wall."  # the ladder is found in chapter 5
        d["chapters"][1]["teaser"] += " The gate was frozen."  # chapter 4's keyword

    probs = problems(frame, early)
    assert any("prologue gives away LADDER" in p for p in probs)
    assert any("chapter 2 teaser gives away FROZEN" in p for p in probs)

    def fine(d: dict) -> None:  # type: ignore[type-arg]
        d["chapters"][5]["teaser"] += " Remember the ladder."  # already found: allowed

    assert problems(frame, fine) == []
    pages, _f, _a = layout_pages(frame, build_puzzles(frame, 7), RenderCtx(7.0, 9.0))
    card = next(p for p in pages if p.title == "Evidence Card 3")
    text = " ".join(str(b.get("text", "")) for b in card.blocks)
    assert "7 names are still on your list" in text and frame.chapters[2].teaser[:20] in text
    assert any(p.title == "Ten Hours Until Dusk" for p in pages)


def test_characters_look_the_same_everywhere(frame: CaseFrame) -> None:
    """Owner rule: one fixed look per character for the whole book and series."""
    assert problems(frame, lambda d: None) == []
    _p, _f, art = layout_pages(frame, build_puzzles(frame, 7), RenderCtx(7.0, 9.0))
    sheets = [a for a in art if a["zone"] == "character_sheet"]
    assert len(sheets) == len(frame.cast) == 16
    wren = next(c for c in frame.cast if c.id == "wren")
    scenes = [a for a in art if "char:greta" in a.get("refs", [])]
    assert scenes and all(
        any(
            c["look"] == next(x for x in frame.cast if x.id == "greta").look
            for c in a["characters"]
        )
        for a in scenes
    )
    assert all(a.get("style") == frame.art_style for a in art if a["zone"] == "scene")

    def changed(d: dict) -> None:  # type: ignore[type-arg]
        d["cast_lock"] = {"wren": wren.look}
        d["cast"][0]["look"] = d["cast"][0]["look"].replace("copper-red braid", "short black hair")

    assert any("differs from the earlier book" in p for p in problems(frame, changed))

    def same_look_new_outfit(d: dict) -> None:  # type: ignore[type-arg]
        d["cast_lock"] = {"wren": wren.look}
        d["cast"][0]["outfit"] = "Summer linen shirt, red scarf tied at the waist, sandals."

    assert problems(frame, same_look_new_outfit) == []

    def glasses(d: dict) -> None:  # type: ignore[type-arg]
        d["cast"][0]["look"] += " Wears round glasses."

    assert any("glasses in the picture text" in p for p in problems(frame, glasses))

    def scarf(d: dict) -> None:  # type: ignore[type-arg]
        d["cast"][1]["outfit"] = d["cast"][1]["outfit"].replace("green scarf", "red scarf")

    assert any("must show a green scarf" in p for p in problems(frame, scarf))

    def missing(d: dict) -> None:  # type: ignore[type-arg]
        d["cast"].pop(4)

    assert any("has no character sheet" in p for p in problems(frame, missing))


def test_art_requests_carry_studio_keys(frame: CaseFrame) -> None:
    _p, _f, art = layout_pages(frame, build_puzzles(frame, 7), RenderCtx(7.0, 9.0))
    ids = {a.get("id") for a in art if a["zone"] != "character_sheet"}
    assert {"cover", "prologue", "portraits"} <= ids
    assert {f"ch{ch.no}" for ch in frame.chapters} <= ids


def test_build_places_studio_art(frame: CaseFrame, tmp_path: Path) -> None:
    from PIL import Image

    art = tmp_path / "art"
    art.mkdir()
    for key in ("cover", "prologue", "ch1", "portraits"):
        Image.new("RGB", (800, 600), (90, 120, 200)).save(art / f"{key}.png")
    man = build_case_book(frame, tmp_path / "book", render=False, art_dir=art)
    assert sorted(man["art"]["placed"]) == ["ch1", "cover", "portraits", "prologue"]
    assert "ch2" in man["art"]["missing"] and man["art"]["pages_added"] == 1
