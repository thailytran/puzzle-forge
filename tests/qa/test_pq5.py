from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge.book.builder import build_book, load_puzzles
from forge.cli import app
from forge.core.book import BookSpec
from forge.qa.checks import REGISTRY, CheckDef, Finding
from forge.qa.fixer import regenerate_failing
from forge.qa.gate import run_gate
from forge.qa.state import StateStore

runner = CliRunner()


def spec() -> BookSpec:
    return BookSpec.model_validate(
        {
            "book": {"title": "Fix Book", "audience": "adult", "content_pages": 6, "seed": 21},
            "puzzles": {"mode": "mixed", "types": [{"type": "sudoku"}, {"type": "maze"}]},
        }
    )


def test_autofix_regenerates_only_failing_puzzle(tmp_path: Path) -> None:
    db = tmp_path / "f.db"
    out = build_book(spec(), tmp_path / "o", db, render=False)
    before = load_puzzles(out)
    target = before[2].id
    saved = dict(REGISTRY)
    try:
        REGISTRY.clear()
        REGISTRY["T.target"] = CheckDef(
            "T.target",
            "BLOCKER",
            "T",
            "",
            lambda ctx: (
                [Finding(message="bad", evidence={"puzzle_id": target})]
                if any(p.id == target for p in ctx.puzzles)
                else []
            ),
        )
        r = run_gate(out, db, fixer=regenerate_failing, max_fix_rounds=2, layers={"T"})
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)
    after = load_puzzles(out)
    assert r.result == "PASSED" and r.fix_rounds == 1
    assert after[2].id != target
    assert [p.id for i, p in enumerate(after) if i != 2] == [
        p.id for i, p in enumerate(before) if i != 2
    ]
    assert json.loads((out / "qa" / "fix_offsets.json").read_text()) == {"2": 30}
    assert (out / "qa" / "qa_report.html").is_file()


@pytest.mark.typst
def test_cli_qa_run_status_and_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "f.db"
    monkeypatch.setenv("FORGE_DB_PATH", str(db))
    out = build_book(spec(), tmp_path / "o", db)
    res = runner.invoke(app, ["qa", "run", str(out)])
    assert res.exit_code == 0, res.output
    assert "PASSED" in res.output
    html = (out / "qa" / "qa_report.html").read_text()
    assert "L1.dual_solver" in html and "page-001.png" in html
    res = runner.invoke(app, ["book", "status", str(out)])
    assert "QA_PASSED" in res.output and "(valid)" in res.output
    # review only from MANUAL_REVIEW
    assert runner.invoke(app, ["review", str(out), "--approve"]).exit_code == 1
    book_id = json.loads((out / "manifest.json").read_text())["book_id"]
    with StateStore(db) as s:
        for to in ("SKU_ASSIGNED", "METADATA_READY", "MANUAL_REVIEW"):
            s.transition(book_id, to)
    res = runner.invoke(app, ["review", str(out), "--reject", "--note", "grid too faint"])
    assert res.exit_code == 0, res.output
    with StateStore(db) as s:
        assert s.current(book_id) == "DRAFT"
    # editing the PDF invalidates a passed report
    runner.invoke(app, ["qa", "run", str(out)])
    (out / "interior.pdf").write_bytes((out / "interior.pdf").read_bytes() + b"\n%x")
    assert "DRAFT" in runner.invoke(app, ["book", "status", str(out)]).output


def test_waive_rejects_major(tmp_path: Path) -> None:
    out = build_book(spec(), tmp_path / "o", tmp_path / "f.db", render=False)
    res = runner.invoke(app, ["qa", "waive", str(out), "L1.difficulty_band", "--reason", "x"])
    assert res.exit_code == 1
