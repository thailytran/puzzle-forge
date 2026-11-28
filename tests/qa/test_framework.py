from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.qa import report as rpt
from forge.qa.checks import REGISTRY, CheckDef, CheckResult, Finding, Skip, run_one
from forge.qa.gate import run_gate, sync_state
from forge.qa.hashlock import file_hashes, is_stale
from forge.qa.state import IllegalTransition, StateStore


def _res(level: str, status: str, id_: str = "X.y") -> CheckResult:
    return CheckResult(id=id_, layer="X", level=level, status=status)  # type: ignore[arg-type]


def _book(tmp: Path) -> Path:
    out = tmp / "book"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps({"book_id": "b1", "puzzles": []}))
    (out / "interior.pdf").write_bytes(b"%PDF-fake")
    return out


# ---------------------------------------------------------------- scoring


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([("BLOCKER", "pass"), ("MAJOR", "pass")], "PASSED"),
        ([("BLOCKER", "fail")], "FAILED"),
        ([("MAJOR", "fail")], "FAILED"),
        ([("MINOR", "fail"), ("BLOCKER", "pass")], "PASSED"),
        ([("BLOCKER", "skip")], "PASSED"),
    ],
)
def test_scoring(tmp_path: Path, results: list[tuple[str, str]], expected: str) -> None:
    out = _book(tmp_path)
    rs = [_res(lv, st, f"X.{i}") for i, (lv, st) in enumerate(results)]
    assert rpt.score("b1", out, rs, rpt.now()).result == expected


def test_check_exception_is_fail() -> None:
    def boom(ctx: object) -> list[Finding]:
        raise RuntimeError("typst missing")

    r = run_one(CheckDef("T.boom", "BLOCKER", "T", "", boom), None)
    assert r.status == "fail"
    assert "typst missing" in r.message


def test_skip() -> None:
    def na(ctx: object) -> list[Finding]:
        raise Skip("not a mystery book")

    assert run_one(CheckDef("T.na", "MAJOR", "T", "", na), None).status == "skip"


def test_waiver_only_minor_and_hash_bound(tmp_path: Path) -> None:
    out = _book(tmp_path)
    with pytest.raises(ValueError):
        rpt.add_waiver(out, "X.major", "because", "owner", "MAJOR")
    rpt.add_waiver(out, "X.minor", "cosmetic", "owner", "MINOR")
    r = rpt.score("b1", out, [_res("MINOR", "fail", "X.minor")], rpt.now())
    assert r.checks[0].waived and r.counts["waived"] == 1
    (out / "interior.pdf").write_bytes(b"%PDF-changed")
    r2 = rpt.score("b1", out, [_res("MINOR", "fail", "X.minor")], rpt.now())
    assert not r2.checks[0].waived  # waiver tied to the old file hashes


# ---------------------------------------------------------------- hash lock


def test_hash_lock(tmp_path: Path) -> None:
    out = _book(tmp_path)
    h = file_hashes(out)
    assert h["cover"] is None and h["interior"]
    assert not is_stale(h, out)
    (out / "manifest.json").write_text("{}")
    assert is_stale(h, out)


# ---------------------------------------------------------------- state machine


def test_state_machine_happy_path(tmp_path: Path) -> None:
    with StateStore(tmp_path / "s.db") as s:
        for to in (
            "QA_RUNNING",
            "QA_PASSED",
            "SKU_ASSIGNED",
            "METADATA_READY",
            "MANUAL_REVIEW",
            "APPROVED",
            "MARKETING_READY",
        ):
            s.transition("b", to)
        assert s.current("b") == "MARKETING_READY"
        assert s.history("b")[0].to_state == "DRAFT"
        assert len(s.history("b")) == 8


def test_illegal_transitions(tmp_path: Path) -> None:
    with StateStore(tmp_path / "s.db") as s:
        with pytest.raises(IllegalTransition):
            s.transition("b", "MANUAL_REVIEW")  # cannot skip QA
        s.transition("b", "QA_RUNNING")
        s.transition("b", "QA_FAILED")
        with pytest.raises(IllegalTransition):
            s.transition("b", "SKU_ASSIGNED")


def test_reject_needs_comment(tmp_path: Path) -> None:
    with StateStore(tmp_path / "s.db") as s:
        for to in ("QA_RUNNING", "QA_PASSED", "SKU_ASSIGNED", "METADATA_READY", "MANUAL_REVIEW"):
            s.transition("b", to)
        with pytest.raises(IllegalTransition):
            s.transition("b", "REJECTED")
        s.transition("b", "REJECTED", actor="owner", note="cover text too small")
        s.transition("b", "DRAFT")
        assert s.history("b")[-2].note == "cover text too small"


# ---------------------------------------------------------------- gate


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, CheckDef]:
    saved = dict(REGISTRY)
    REGISTRY.clear()
    monkeypatch.setattr("forge.qa.gate.CHECK_MODULES", ())
    yield REGISTRY
    REGISTRY.clear()
    REGISTRY.update(saved)


def test_gate_pass_then_stale(tmp_path: Path, isolated_registry: dict[str, CheckDef]) -> None:
    out = _book(tmp_path)
    isolated_registry["T.ok"] = CheckDef("T.ok", "BLOCKER", "T", "", lambda ctx: [])
    r = run_gate(out, tmp_path / "s.db")
    assert r.result == "PASSED"
    with StateStore(tmp_path / "s.db") as s:
        assert s.current("b1") == "QA_PASSED"
        (out / "interior.pdf").write_bytes(b"%PDF-edited")
        assert sync_state(s, "b1", out) == "DRAFT"


def test_gate_autofix_rounds(tmp_path: Path, isolated_registry: dict[str, CheckDef]) -> None:
    out = _book(tmp_path)
    state = {"broken": True, "calls": 0}

    def flaky(ctx: object) -> list[Finding]:
        return (
            [Finding(message="bad puzzle", evidence={"puzzle_id": "p1"})] if state["broken"] else []
        )

    def fixer(ctx: object, report: rpt.QaReport) -> bool:
        state["calls"] += 1
        state["broken"] = False
        return True

    isolated_registry["T.flaky"] = CheckDef("T.flaky", "BLOCKER", "T", "", flaky)
    r = run_gate(out, tmp_path / "s.db", fixer=fixer, max_fix_rounds=3)
    assert r.result == "PASSED" and r.fix_rounds == 1 and state["calls"] == 1


def test_gate_gives_up_after_n_rounds(
    tmp_path: Path, isolated_registry: dict[str, CheckDef]
) -> None:
    out = _book(tmp_path)
    isolated_registry["T.bad"] = CheckDef(
        "T.bad", "MAJOR", "T", "", lambda ctx: [Finding(message="still bad")]
    )
    r = run_gate(out, tmp_path / "s.db", fixer=lambda c, rep: True, max_fix_rounds=2)
    assert r.result == "FAILED" and r.fix_rounds == 2
    with StateStore(tmp_path / "s.db") as s:
        assert s.current("b1") == "QA_FAILED"
