"""QA report: scoring (0 BLOCKER + 0 MAJOR fails), waivers (MINOR only), persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from forge.qa.checks import CheckResult
from forge.qa.hashlock import file_hashes, is_stale

QA_DIR = "qa"


class Waiver(BaseModel):
    check_id: str
    reason: str
    by: str
    at: str
    hashes: dict[str, str | None]


class QaReport(BaseModel):
    book_id: str
    run_id: str
    started: str
    finished: str
    result: Literal["PASSED", "FAILED"]
    hashes: dict[str, str | None]
    counts: dict[str, int]
    checks: list[CheckResult]
    fix_rounds: int = 0
    notes: list[str] = Field(default_factory=list)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def load_waivers(out_dir: Path) -> list[Waiver]:
    p = out_dir / QA_DIR / "waivers.json"
    if not p.is_file():
        return []
    return [Waiver.model_validate(w) for w in json.loads(p.read_text(encoding="utf-8"))]


def add_waiver(out_dir: Path, check_id: str, reason: str, by: str, level: str) -> Waiver:
    if level != "MINOR":
        raise ValueError(f"{check_id} is {level}: only MINOR checks can be waived")
    if not reason.strip():
        raise ValueError("a waiver needs a reason")
    w = Waiver(check_id=check_id, reason=reason, by=by, at=now(), hashes=file_hashes(out_dir))
    ws = [x for x in load_waivers(out_dir) if x.check_id != check_id] + [w]
    (out_dir / QA_DIR).mkdir(parents=True, exist_ok=True)
    (out_dir / QA_DIR / "waivers.json").write_text(
        json.dumps([x.model_dump() for x in ws], indent=1), encoding="utf-8"
    )
    return w


def score(
    book_id: str, out_dir: Path, results: list[CheckResult], started: str, fix_rounds: int = 0
) -> QaReport:
    hashes = file_hashes(out_dir)
    valid_waivers = {w.check_id for w in load_waivers(out_dir) if w.hashes == hashes}
    for r in results:
        r.waived = r.status == "fail" and r.level == "MINOR" and r.id in valid_waivers
    fails = [r for r in results if r.status == "fail"]
    counts = {
        "blocker_fail": sum(r.level == "BLOCKER" for r in fails),
        "major_fail": sum(r.level == "MAJOR" for r in fails),
        "minor_fail": sum(r.level == "MINOR" and not r.waived for r in fails),
        "waived": sum(r.waived for r in fails),
        "passed": sum(r.status == "pass" for r in results),
        "skipped": sum(r.status == "skip" for r in results),
    }
    ok = counts["blocker_fail"] == 0 and counts["major_fail"] == 0
    return QaReport(
        book_id=book_id,
        run_id=f"qa-{started.replace(':', '').replace('-', '')}",
        started=started,
        finished=now(),
        result="PASSED" if ok else "FAILED",
        hashes=hashes,
        counts=counts,
        checks=results,
        fix_rounds=fix_rounds,
    )


def save(report: QaReport, out_dir: Path) -> Path:
    d = out_dir / QA_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / "qa_report.json"
    p.write_text(report.model_dump_json(indent=1), encoding="utf-8")
    return p


def load(out_dir: Path) -> QaReport | None:
    p = out_dir / QA_DIR / "qa_report.json"
    return QaReport.model_validate_json(p.read_text(encoding="utf-8")) if p.is_file() else None


def report_valid(out_dir: Path) -> bool:
    """A PASSED report counts only while the locked files are unchanged."""
    r = load(out_dir)
    return r is not None and r.result == "PASSED" and not is_stale(r.hashes, out_dir)
