"""Adventure case frame: structure, logic lock, puzzles and reader run (ROADMAP P9.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.adventure.frame import (
    AdventureFrame,
    build_puzzles,
    check_frame,
    code_type,
    count_codes,
    load_frame,
    lock_check,
    simulate_reader,
)
from forge.adventure.objects import (
    CATALOG,
    MIN_OBJECTS,
    icon_sheet_brief,
    object_problems,
    pick_objects,
)

FRAME = Path(__file__).resolve().parents[2] / "configs/adventures/snow_queens_library.json"


@pytest.fixture(scope="module")
def frame() -> AdventureFrame:
    return load_frame(FRAME)


def _copy(frame: AdventureFrame) -> AdventureFrame:
    return AdventureFrame.model_validate(frame.model_dump())


def test_snow_queen_frame_passes_every_check(frame: AdventureFrame) -> None:
    rep = check_frame(frame, seed=7, deep=True)
    assert rep.ok, rep.feedback()
    assert rep.lock["count_all"] == 1
    assert all(c > 1 for c in rep.lock["without_key"].values())


def test_reader_reads_the_final_word(frame: AdventureFrame) -> None:
    run = simulate_reader(frame, build_puzzles(frame, 11))
    assert run.ok, run.problems
    assert run.word == "EVERGLOW"


def test_puzzles_are_deterministic(frame: AdventureFrame) -> None:
    a = [(p.a.content_hash, p.b.content_hash) for p in build_puzzles(frame, 5)]
    b = [(p.a.content_hash, p.b.content_hash) for p in build_puzzles(frame, 5)]
    assert a == b


def test_count_codes() -> None:
    assert count_codes(3, {1: "A", 2: "B", 3: "C"}, []) == 1
    assert count_codes(3, {1: "A", 2: "B"}, []) == 26
    assert count_codes(3, {1: "A"}, ["B"]) == 2 * 26  # B in slot 2 or 3, any letter in the other
    assert count_codes(3, {1: "A"}, ["B", "B"]) == 1


def test_lock_without_a_key_is_open(frame: AdventureFrame) -> None:
    lock = lock_check(frame)
    assert lock.count_all == 1
    assert set(lock.drop_letter.values()) == {26}


def test_wrong_key_letter_is_refused(frame: AdventureFrame) -> None:
    f = _copy(frame)
    f.chapters[0].key.letter = "Q"
    assert any("first letter" in p for p in check_frame(f, deep=False).problems)


def test_slots_must_spell_the_final_word(frame: AdventureFrame) -> None:
    f = _copy(frame)
    f.chapters[0].puzzle_b.digit = f.chapters[0].key.slot = f.chapters[1].key.slot
    probs = check_frame(f, deep=False).problems
    assert any("every slot" in p for p in probs)


def test_answer_leak_is_refused(frame: AdventureFrame) -> None:
    f = _copy(frame)
    f.chapters[0].story += " A raven watches you."
    assert any("leak" in p for p in check_frame(f, deep=False).problems)


def test_final_word_leak_is_refused(frame: AdventureFrame) -> None:
    f = _copy(frame)
    f.prologue += " Everglow, she says."
    assert any("final word" in p and "leak" in p for p in check_frame(f, deep=False).problems)


def test_unknown_type_is_refused(frame: AdventureFrame) -> None:
    f = _copy(frame)
    f.chapters[5].puzzle_a.type = "Logic Grid"
    assert any("cannot give a verified word" in p for p in check_frame(f, deep=False).problems)


def test_message_must_end_with_answer(frame: AdventureFrame) -> None:
    f = _copy(frame)
    f.chapters[4].puzzle_a.message = "The stars whisper to the glass tonight"
    assert any("must end with" in p for p in check_frame(f, deep=False).problems)


def test_type_labels() -> None:
    assert code_type("Word Scramble") == "scramble"
    assert code_type("Sudoku (6\u00d76)", "b") == "sudoku"
    assert code_type("Fill-in Crossword") == ""


def test_object_rules() -> None:
    ok = list(CATALOG)[:MIN_OBJECTS]
    assert object_problems(ok, ["RAVEN"]) == []
    assert any("twice" in p for p in object_problems([*ok[:-1], ok[0]], []))
    assert any("not in the catalog" in p for p in object_problems([*ok[:-1], "laser sword"], []))
    assert any("answer" in p for p in object_problems([*ok[:-1], "lantern"], ["LANTERN"]))
    assert any("12-20" in p for p in object_problems(ok[:5], []))


def test_pick_objects_is_deterministic_and_clean() -> None:
    a = pick_objects(["garden"], 12, seed=3, answers=("ROSE",))
    assert a == pick_objects(["garden"], 12, seed=3, answers=("ROSE",))
    assert len(set(a)) == 12 and "rose" not in a
    assert object_problems(a, ["ROSE"]) == []


def test_icon_sheet_brief_lists_objects_in_order() -> None:
    brief = icon_sheet_brief(["teacup", "quill", "candle"], cols=3)
    assert "1. teacup; 2. quill; 3. candle" in brief
    assert "3 columns x 1 rows" in brief
