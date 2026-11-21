from __future__ import annotations

import copy
from pathlib import Path

from forge.mystery.series_variety import check_series, load_series

BIBLE = Path(__file__).resolve().parents[2] / "configs" / "series" / "tamsin_hale.json"


def test_tamsin_hale_series_is_varied() -> None:
    assert check_series(load_series(BIBLE)) == []


def test_repeated_mechanic_is_rejected() -> None:
    s = copy.deepcopy(load_series(BIBLE))
    s["volumes"][1]["clue_mechanic"] = s["volumes"][0]["clue_mechanic"]
    assert any("repeated" in p for p in check_series(s))


def test_similar_game_sets_are_rejected() -> None:
    s = copy.deepcopy(load_series(BIBLE))
    s["volumes"][1]["games"] = list(s["volumes"][0]["games"])
    assert any("too similar" in p for p in check_series(s))


def test_no_new_types_is_rejected() -> None:
    s = copy.deepcopy(load_series(BIBLE))
    s["volumes"][2]["games"] = ["maze", "sudoku", "numlock", "shift", "wordsearch", "cbn"]
    s["volumes"][2]["twists"] = {}
    assert any("new/twisted" in p for p in check_series(s))
