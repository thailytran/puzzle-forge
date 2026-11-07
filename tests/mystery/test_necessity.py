import pytest

from forge.mystery.necessity import CaseError, check_case, holds

SUSPECTS = [
    {"name": "Captain Reed", "hat": "red", "place": "harbor", "height": 180},
    {"name": "Mira Vance", "hat": "blue", "place": "harbor", "height": 165},
    {"name": "Otto Kling", "hat": "red", "place": "library", "height": 170},
    {"name": "June Park", "hat": "green", "place": "harbor", "height": 182},
]


def case(clues):
    return {"space": {"candidates": SUSPECTS}, "clues": clues, "answer": "Captain Reed"}


GOOD = [
    {"id": "hat", "field": "hat", "op": "eq", "value": "red"},
    {"id": "place", "field": "place", "op": "eq", "value": "harbor"},
]


def test_all_clues_needed_passes():
    rep = check_case(case(GOOD))
    assert rep.ok and rep.solutions == ["Captain Reed"]
    assert rep.dropped["hat"] == ["Captain Reed", "Mira Vance", "June Park"]


def test_redundant_clue_is_reported():
    rep = check_case(case([*GOOD, {"id": "tall", "field": "height", "op": "ge", "value": 175}]))
    assert not rep.ok
    assert rep.redundant == ["place", "tall"]
    assert any("not needed" in p for p in rep.problems())


def test_ambiguous_and_wrong_answer():
    rep = check_case(case(GOOD[:1]))
    assert not rep.unique and not rep.ok
    rep = check_case({**case(GOOD), "answer": "Otto Kling"})
    assert not rep.ok and "declared answer" in rep.problems()[0]


def test_code_space_with_derived_fields():
    clues = [
        {"id": "first", "field": "d1", "op": "in", "value": ["4", "5"]},
        {"id": "last", "field": "d2", "op": "in", "value": ["2", "7"]},
        {"id": "sum", "field": "sum", "op": "eq", "value": 11},
    ]
    rep = check_case({"space": {"code": {"length": 2}}, "clues": clues, "answer": "47"})
    assert rep.ok, rep.problems()
    assert rep.dropped["first"] == ["47", "92"]
    rep = check_case(
        {
            "space": {"code": {"length": 2}},
            "clues": [*clues, {"id": "x", "field": "d2", "op": "ne", "value": "2"}],
        }
    )
    assert rep.redundant


def test_combinators_and_errors():
    c = SUSPECTS[0]
    assert holds(
        {
            "any_of": [
                {"field": "hat", "op": "eq", "value": "x"},
                {"field": "hat", "op": "eq", "value": "red"},
            ]
        },
        c,
    )
    assert holds({"all_of": [{"field": "height", "op": "gt", "value": 100}]}, c)
    assert holds({"distinct": ["hat", "place"]}, c)
    with pytest.raises(CaseError):
        holds({"field": "nope", "op": "eq", "value": 1}, c)
    with pytest.raises(CaseError):
        check_case({"space": {"code": {"length": 9}}, "clues": GOOD})
