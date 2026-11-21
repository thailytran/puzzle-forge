"""Auto-fix for classic books: regenerate puzzles named in failing checks with fresh seeds.

Never edits output by hand: it shifts the seed range of the failing slots (qa/fix_offsets.json)
and rebuilds the whole book, so the result is still deterministic from spec + offsets.
"""

from __future__ import annotations

import json
from typing import Any

from forge.book.builder import FIX_OFFSETS, MAX_SEED_TRIES, build_book, load_offsets
from forge.core.book import BookSpec
from forge.qa.report import QaReport


def failing_slots(ctx: Any, report: QaReport) -> set[int]:
    ids = {
        f.evidence.get("puzzle_id")
        for c in report.checks
        if c.status == "fail" and not c.waived
        for f in c.findings
    }
    return {row["n"] - 1 for row in ctx.manifest["puzzles"] if row["id"] in ids}


def regenerate_failing(ctx: Any, report: QaReport) -> bool:
    slots = failing_slots(ctx, report)
    if not slots:
        return False  # failure is not tied to a puzzle: needs a human / code fix
    offsets = load_offsets(ctx.out_dir)
    for s in slots:
        offsets[s] = offsets.get(s, 0) + MAX_SEED_TRIES
    p = ctx.out_dir / FIX_OFFSETS
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({str(k): v for k, v in sorted(offsets.items())}), encoding="utf-8")
    spec = BookSpec.model_validate(ctx.manifest["spec"])
    build_book(spec, ctx.out_dir.parent, ctx.db_path, render=ctx.pdf_path.is_file())
    return True
