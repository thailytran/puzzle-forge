from types import SimpleNamespace

from forge.vault.rules import answer_problems, site_problems


def test_answer_rules():
    assert (
        answer_problems("culprit_name", ["Captain Reed", "Reed"], [], ["Captain Reed", "Mabel Fry"])
        == []
    )
    amb = answer_problems("culprit_name", ["Ivy Marsh", "Marsh"], [], ["Ivy Marsh", "Otis Marsh"])
    assert any("R3" in x for x in amb)
    assert any("R2" in x for x in answer_problems("culprit_name", ["Nobody"], [], ["Ivy Marsh"]))
    assert any("R4" in x for x in answer_problems("unlock_code", [], ["1111"]))
    assert any("R4" in x for x in answer_problems("unlock_code", [], ["1234"]))
    assert answer_problems("unlock_code", [], ["4729"]) == []
    assert any("R2" in x for x in answer_problems("unlock_code", [], ["47#29"]))
    assert any(
        "R4" in x
        for x in answer_problems("culprit_name", ["Bartholomew Featherstonehaugh"], [], kids=True)
    )


def test_site_rules():
    ok = SimpleNamespace(
        book_code_prefix="CASE01",
        series_id="s",
        series_order=2,
        series_total=10,
        next_book_id="b3",
        extended_ending="word " * 120,
    )
    assert site_problems(ok, "PF-CASE-002") == []
    last = SimpleNamespace(**{**vars(ok), "series_order": 10, "next_book_id": "x"})
    assert any("R7" in x for x in site_problems(last, "b"))
    bad = SimpleNamespace(
        **{**vars(ok), "book_code_prefix": "c1", "series_total": 20, "next_book_id": ""}
    )
    probs = site_problems(bad, "bad id/with slash")
    assert {x[:2] for x in probs} >= {"R5", "R6", "R7"}
