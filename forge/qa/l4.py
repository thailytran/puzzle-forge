"""L4 — mystery / escape logic (docs/QA_SPEC.md §3 L4, MYSTERY_DESIGN.md §15)."""

from __future__ import annotations

from typing import Any

from forge.mystery.necessity import check_case
from forge.qa.checks import Finding, Skip, check


def _cases(ctx: Any) -> list[dict[str, Any]]:
    case = ctx.manifest.get("case")
    if not case:
        raise Skip("classic book: no case / final answer")
    finals = case.get("finals") or [case]
    return [f for f in finals if f.get("clues")]


@check(
    "L4.all_clues_required",
    "BLOCKER",
    "Final answer needs every clue: all clues -> 1 candidate, any clue dropped -> > 1",
)
def all_clues_required(ctx: Any) -> list[Finding]:
    out = []
    finals = _cases(ctx)
    if not finals:
        return [Finding(message="case has no declarative clues for the final answer")]
    for f in finals:
        rep = check_case(f)
        for p in rep.problems():
            out.append(
                Finding(
                    message=f"{f.get('kind', 'final')}: {p}",
                    evidence={"survivors_without": rep.dropped, "solutions": rep.solutions[:10]},
                )
            )
    return out
