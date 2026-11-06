"""Word search → layout blocks (rendered by templates/typst/book.typ)."""

from __future__ import annotations

from typing import Any

from forge.core.models import HiddenMessage, Puzzle
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.puzzles.base import find_constraint
from forge.puzzles.wordsearch.grid import MASKED
from forge.puzzles.wordsearch.params import DIRS

MIN_CELL_IN = {"kids_6_8": 0.45, "senior_large_print": 0.4}


def _cell_size(puzzle: Puzzle, ctx: RenderCtx, grid_share: float) -> float:
    rows: list[str] = puzzle.data["rows"]
    nr, nc = len(rows), len(rows[0])
    cell = min(ctx.width_in / nc, ctx.height_in * grid_share / nr, 0.6)
    return round(cell, 3)


def _grid_rows(puzzle: Puzzle) -> list[list[str | None]]:
    return [[None if ch == MASKED else ch for ch in row] for row in puzzle.data["rows"]]


def _font_pt(cell_in: float, ctx: RenderCtx) -> float:
    base = cell_in * 72 * 0.55
    if ctx.large_print:
        base = max(base, 16.0)
    return round(min(base, cell_in * 72 * 0.8), 1)


def _column_major(words: list[str], columns: int) -> list[str]:
    per_col = -(-len(words) // columns)
    cols = [words[i * per_col : (i + 1) * per_col] for i in range(columns)]
    out: list[str] = []
    for r in range(per_col):
        for col in cols:
            out.append(col[r] if r < len(col) else "")
    return out


def render(puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
    cell = _cell_size(puzzle, ctx, grid_share=0.68)
    words = sorted(puzzle.data["words"])
    columns = 3 if len(words) <= 15 or ctx.width_in < 5.5 else 4
    blocks: list[dict[str, Any]] = [
        {
            "kind": "letter_grid",
            "rows": _grid_rows(puzzle),
            "cell_in": cell,
            "font_pt": _font_pt(cell, ctx),
        },
        {"kind": "spacer", "height_in": 0.2},
        {
            "kind": "word_list",
            "words": _column_major(words, columns),
            "columns": columns,
            "font_pt": 16.0 if ctx.large_print else 11.0,
        },
    ]
    if find_constraint(puzzle.spec, HiddenMessage) is not None:
        blocks.append(
            {
                "kind": "paragraph",
                "text": "Secret message: the letters you did not circle, read left to right "
                "and top to bottom, spell a hidden message.",
            }
        )
    return RenderedBlock(blocks=blocks)


def render_solution(puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
    cell = _cell_size(puzzle, ctx, grid_share=1.0)
    highlights = []
    for p in puzzle.solution["placements"]:
        dr, dc = DIRS[p["dir"]]
        n = len(p["word"]) - 1
        highlights.append([p["row"], p["col"], p["row"] + n * dr, p["col"] + n * dc])
    return RenderedBlock(
        blocks=[
            {
                "kind": "letter_grid",
                "rows": _grid_rows(puzzle),
                "cell_in": cell,
                "font_pt": _font_pt(cell, ctx),
                "highlights": highlights,
            }
        ]
    )
