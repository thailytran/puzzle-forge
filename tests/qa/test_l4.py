from types import SimpleNamespace

from forge.qa.checks import REGISTRY, run_one
from forge.qa.gate import CHECK_MODULES

SPACE = {
    "candidates": [
        {"name": n, "hat": h, "place": p}
        for n, h, p in [
            ("Reed", "red", "harbor"),
            ("Vance", "blue", "harbor"),
            ("Kling", "red", "library"),
        ]
    ]
}
CLUES = [
    {"id": "a", "field": "hat", "op": "eq", "value": "red"},
    {"id": "b", "field": "place", "op": "eq", "value": "harbor"},
]


def run(manifest):
    assert "forge.qa.l4" in CHECK_MODULES
    import forge.qa.l4  # noqa: F401

    return run_one(REGISTRY["L4.all_clues_required"], SimpleNamespace(manifest=manifest))


def test_classic_book_skips():
    assert run({}).status == "skip"


def test_pass_and_fail():
    ok = {"case": {"space": SPACE, "clues": CLUES, "answer": "Reed"}}
    assert run(ok).status == "pass"
    bad = {
        "case": {
            "finals": [{"kind": "culprit", "space": SPACE, "clues": CLUES[:1], "answer": "Reed"}]
        }
    }
    r = run(bad)
    assert r.status == "fail" and r.level == "BLOCKER" and "2 candidates" in r.message
