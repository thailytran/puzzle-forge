"""Run the QA gate for a built book: state transitions, checks, scoring, auto-fix rounds."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from forge.core.models import Puzzle
from forge.qa import report as rpt
from forge.qa.checks import run_checks
from forge.qa.state import StateStore

CHECK_MODULES = ("forge.qa.l1", "forge.qa.l2", "forge.qa.l3", "forge.qa.l2_editions")
REVIEWABLE = "MANUAL_REVIEW"
DEFAULT_MAX_FIX_ROUNDS = 3


def load_check_modules() -> None:
    for m in CHECK_MODULES:
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as exc:
            if exc.name != m:
                raise


@dataclass
class BookContext:
    out_dir: Path
    db_path: Path
    extra: dict[str, Any] = field(default_factory=dict)

    @cached_property
    def manifest(self) -> dict[str, Any]:
        return dict(json.loads((self.out_dir / "manifest.json").read_text(encoding="utf-8")))

    @property
    def book_id(self) -> str:
        return str(self.manifest["book_id"])

    @cached_property
    def puzzles(self) -> list[Puzzle]:
        from forge.book.builder import load_puzzles

        return load_puzzles(self.out_dir)

    @property
    def pdf_path(self) -> Path:
        return self.out_dir / "interior.pdf"


Fixer = Callable[[BookContext, rpt.QaReport], bool]  # returns True if it changed the book


def sync_state(store: StateStore, book_id: str, out_dir: Path) -> str:
    """Drop the book back to DRAFT when a passed report no longer matches the files."""
    cur = store.ensure(book_id)
    if cur not in ("DRAFT", "QA_RUNNING", "QA_FAILED") and not rpt.report_valid(out_dir):
        store.transition(book_id, "DRAFT", note="files changed after QA: report invalidated")
        return "DRAFT"
    return cur


def run_gate(
    out_dir: Path,
    db_path: Path,
    fixer: Fixer | None = None,
    max_fix_rounds: int = DEFAULT_MAX_FIX_ROUNDS,
    layers: set[str] | None = None,
) -> rpt.QaReport:
    load_check_modules()
    ctx = BookContext(out_dir, db_path)
    book_id = ctx.book_id
    with StateStore(db_path) as store:
        cur = sync_state(store, book_id, out_dir)
        if cur not in ("DRAFT", "QA_FAILED"):
            store.transition(book_id, "DRAFT", note="re-running QA")
        rounds = 0
        while True:
            store.transition(book_id, "QA_RUNNING", note=f"round {rounds}")
            started = rpt.now()
            results = run_checks(ctx, layers)
            report = rpt.score(book_id, out_dir, results, started, fix_rounds=rounds)
            rpt.save(report, out_dir)
            from forge.qa.html import render_html

            render_html(report, out_dir)
            if report.result == "PASSED":
                store.transition(book_id, "QA_PASSED", note=report.run_id)
                return report
            store.transition(book_id, "QA_FAILED", note=_summary(report))
            if fixer is None or rounds >= max_fix_rounds or not fixer(ctx, report):
                return report
            rounds += 1
            ctx = BookContext(out_dir, db_path)  # reload changed files


def _summary(r: rpt.QaReport) -> str:
    failed = [c.id for c in r.checks if c.status == "fail" and not c.waived]
    return f"{r.counts['blocker_fail']} blocker, {r.counts['major_fail']} major: " + ", ".join(
        failed[:8]
    )
