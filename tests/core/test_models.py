from __future__ import annotations

import pytest
from pydantic import ValidationError

from forge.core.models import (
    AnswerIs,
    DifficultyScore,
    HiddenMessage,
    PuzzleSpec,
    ShadedCells,
    VerifyReport,
    build_puzzle,
    level_from_score,
)


def _spec(**kw: object) -> PuzzleSpec:
    base: dict[str, object] = {"type": "wordsearch", "level": "easy", "audience": "adult"}
    base.update(kw)
    return PuzzleSpec.model_validate(base)


def test_spec_defaults() -> None:
    s = _spec()
    assert s.options == {}
    assert s.constraints == []


def test_spec_rejects_unknown_level() -> None:
    with pytest.raises(ValidationError):
        _spec(level="impossible")


def test_constraints_discriminated() -> None:
    s = _spec(
        constraints=[
            {"kind": "hidden_message", "text": "HARBOR"},
            {"kind": "shaded_cells", "cells": [[0, 1], [2, 3]], "expect": "47"},
            {"kind": "answer_is", "word": "KEY"},
        ]
    )
    assert isinstance(s.constraints[0], HiddenMessage)
    assert isinstance(s.constraints[1], ShadedCells)
    assert s.constraints[1].cells == [(0, 1), (2, 3)]
    assert isinstance(s.constraints[2], AnswerIs)


def test_constraint_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        _spec(constraints=[{"kind": "nope"}])


def test_build_puzzle_hash_and_id_deterministic() -> None:
    a = build_puzzle(_spec(), seed=1, data={"grid": ["AB", "CD"]}, solution={"x": 1})
    b = build_puzzle(_spec(), seed=1, data={"grid": ["AB", "CD"]}, solution={"x": 1})
    assert a.content_hash == b.content_hash
    assert a.id == b.id
    assert a.model_dump_json() == b.model_dump_json()
    assert a.id.startswith("wordsearch-")


def test_hash_depends_on_data_only() -> None:
    a = build_puzzle(_spec(), seed=1, data={"grid": ["AB"]}, solution={})
    b = build_puzzle(_spec(level="hard"), seed=99, data={"grid": ["AB"]}, solution={"s": 2})
    assert a.content_hash == b.content_hash


def test_difficulty_score_bounds() -> None:
    with pytest.raises(ValidationError):
        DifficultyScore(score=120, label="hard", features={})


def test_level_from_score() -> None:
    assert level_from_score(0) == "very_easy"
    assert level_from_score(30) == "easy"
    assert level_from_score(50) == "medium"
    assert level_from_score(70) == "hard"
    assert level_from_score(100) == "expert"


def test_verify_report_roundtrip() -> None:
    r = VerifyReport(ok=True, unique=True, solver="ref", messages=["fine"])
    assert VerifyReport.model_validate_json(r.model_dump_json()) == r
