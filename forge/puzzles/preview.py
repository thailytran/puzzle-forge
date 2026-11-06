"""Single-puzzle preview PDF (puzzle page + solution page) for `forge puzzle`."""

from __future__ import annotations

from pathlib import Path

from forge.core.models import Puzzle
from forge.core.protocol import RenderCtx
from forge.layout.document import Page, make_layout, render_pdf
from forge.layout.trim import TRIMS, margins_for
from forge.puzzles.registry import get_puzzle_type

TITLE_SPACE_IN = 0.9  # heading + running header + footer


def content_ctx(trim: str, large_print: bool = False, pages: int = 2) -> RenderCtx:
    t = TRIMS[trim]
    m = margins_for(max(pages, 24))
    return RenderCtx(
        width_in=t.width_in - m.inside - m.outside,
        height_in=t.height_in - m.top - m.bottom - TITLE_SPACE_IN,
        large_print=large_print,
    )


def puzzle_title(puzzle: Puzzle) -> str:
    theme = (puzzle.spec.theme or puzzle.type).replace("_", " ").title()
    return theme


def preview_pdf(puzzle: Puzzle, out: Path, trim: str = "8.5x11") -> Path:
    pt = get_puzzle_type(puzzle.type)
    large = puzzle.spec.audience == "senior_large_print"
    ctx = content_ctx(trim, large)
    pages = [
        Page(kind="puzzle", title=puzzle_title(puzzle), blocks=pt.render(puzzle, ctx).blocks),
        Page(kind="solutions", title="Solution", blocks=pt.render_solution(puzzle, ctx).blocks),
    ]
    doc = make_layout(
        title=f"{puzzle.type} preview", trim=trim, pages=pages, large_print=large, min_pages=0
    )
    return render_pdf(doc, out)
