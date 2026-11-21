from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.book.builder import BuildError, build_book, load_puzzles
from forge.book.content_plan import ContentPlan, load_plan, save_plan, validate_plan
from forge.book.plan import plan_book
from forge.core.book import BookSpec

OCEAN = {
    "Coral Reef": [
        "CORAL",
        "REEF",
        "FISH",
        "CLAM",
        "SPONGE",
        "ANEMONE",
        "EEL",
        "SHRIMP",
        "SNAIL",
        "CRAB",
        "STARFISH",
        "TURTLE",
    ],
    "Beach Day": [
        "SAND",
        "TOWEL",
        "BUCKET",
        "SHOVEL",
        "SHELL",
        "WAVE",
        "SUN",
        "HAT",
        "BALL",
        "KITE",
        "UMBRELLA",
        "PICNIC",
    ],
    "Sea Mammals": [
        "WHALE",
        "DOLPHIN",
        "SEAL",
        "OTTER",
        "WALRUS",
        "MANATEE",
        "ORCA",
        "PORPOISE",
        "CALF",
        "POD",
        "FLIPPER",
        "BLUBBER",
    ],
}


def spec(pages: int = 3, audience: str = "adult") -> BookSpec:
    return BookSpec.model_validate(
        {
            "book": {
                "title": "Ocean Plan",
                "audience": audience,
                "content_pages": pages,
                "seed": 4,
            },
            "puzzles": {
                "mode": "progressive",
                "distribution": {"very_easy": 1},
                "types": [{"type": "wordsearch"}],
            },
        }
    )


def plan(**over: object) -> ContentPlan:
    pages = [
        {
            "n": i + 1,
            "type": "wordsearch",
            "level": "very_easy",
            "subtheme": name,
            "words": words,
            "illustration": f"A friendly scene: {', '.join(words[:3]).lower()}",
        }
        for i, (name, words) in enumerate(OCEAN.items())
    ]
    data: dict[str, object] = {"book_theme": "Ocean", "audience": "adult", "pages": pages}
    data.update(over)
    return ContentPlan.model_validate(data)


def test_valid_plan() -> None:
    assert validate_plan(plan(), plan_book(spec()), "adult") == []


def test_duplicate_subtheme_and_overused_word() -> None:
    p = plan()
    p.pages[1].subtheme = "Coral Reef"
    p.pages[1].words = list(OCEAN["Coral Reef"])
    p.pages[2].words = list(OCEAN["Coral Reef"])
    problems = validate_plan(p, plan_book(spec()), "adult")
    assert any("sub-theme used on 2 pages" in x for x in problems)
    assert any("CORAL used on 3 pages" in x for x in problems)


def test_too_few_words_and_unknown_word() -> None:
    p = plan()
    p.pages[0].words = ["CORAL", "ZZXQW"]
    problems = validate_plan(p, plan_book(spec()), "adult")
    assert any("needs ≥ 12" in x for x in problems)  # adult Beginner (content_rules.yaml)
    assert any("ZZXQW not in dictionary" in x for x in problems)


def test_glossary_allows_topic_terms() -> None:
    p = plan(glossary=["NUDIBRANCH"])
    p.pages[0].words = [*OCEAN["Coral Reef"], "NUDIBRANCH"]
    assert validate_plan(p, plan_book(spec()), "adult") == []


def test_kids_word_must_be_common() -> None:
    p = plan()
    p.pages[0].words = [*OCEAN["Coral Reef"][:11], "BIOLUMINESCENCE"]
    problems = validate_plan(p, plan_book(spec(audience="kids_6_8")), "kids_6_8")
    assert any("BIOLUMINESCENCE not a common kids' word" in x for x in problems)


def test_roundtrip_yaml(tmp_path: Path) -> None:
    save_plan(plan(), tmp_path / "p.yaml")
    assert load_plan(tmp_path / "p.yaml") == plan()


def test_builder_uses_plan(tmp_path: Path) -> None:
    out = build_book(spec(), tmp_path / "o", tmp_path / "f.db", render=False, plan=plan())
    pz = load_puzzles(out)
    for p, (name, words) in zip(pz, OCEAN.items(), strict=True):
        assert p.spec.theme == name
        assert set(p.data["words"]) <= set(words)
    req = json.loads((out / "illustration_requests.json").read_text())
    assert [r["subtheme"] for r in req] == list(OCEAN)
    assert (out / "content_plan.yaml").is_file()
    # --from-stage puzzles: a later build reuses the saved (possibly hand-edited) plan
    again = build_book(spec(), tmp_path / "o", tmp_path / "f.db", render=False)
    assert [p.id for p in load_puzzles(again)] == [p.id for p in pz]


def test_builder_rejects_invalid_plan(tmp_path: Path) -> None:
    p = plan()
    p.pages[0].words = ["CORAL"]
    with pytest.raises(BuildError, match="content plan invalid"):
        build_book(spec(), tmp_path / "o", tmp_path / "f.db", render=False, plan=p)
