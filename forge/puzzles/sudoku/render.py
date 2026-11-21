"""Sudoku → `sudoku_grid` layout block."""

from __future__ import annotations

from typing import Any

from forge.core.models import Puzzle, ShadedCells
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.puzzles.base import find_constraint
from forge.puzzles.sudoku.grid import box_shape


def _block(puzzle: Puzzle, ctx: RenderCtx, solution: bool, share: float) -> dict[str, Any]:
    n = int(puzzle.data["size"])
    br, bc = box_shape(n)
    givens = puzzle.data["givens"]
    sol = puzzle.solution["grid"]
    cell = round(min(ctx.width_in / n, ctx.height_in * share / n, 0.75), 3)
    font = round(cell * 72 * 0.55, 1)
    if ctx.large_print:
        font = max(font, 18.0)
    sc = find_constraint(puzzle.spec, ShadedCells)
    return {
        "kind": "sudoku_grid",
        "size": n,
        "box_rows": br,
        "box_cols": bc,
        "cells": [
            [(sol[r][c] if solution else givens[r][c]) or None for c in range(n)] for r in range(n)
        ],
        "given_mask": [[bool(givens[r][c]) for c in range(n)] for r in range(n)],
        "shaded": [list(x) for x in sc.cells] if sc else [],
        "cell_in": cell,
        "font_pt": font,
    }


def render(puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
    blocks: list[dict[str, Any]] = [_block(puzzle, ctx, False, 0.8)]
    if find_constraint(puzzle.spec, ShadedCells):
        blocks.append(
            {
                "kind": "paragraph",
                "text": "Code: write the digits from the shaded squares, top to bottom, "
                "left to right.",
            }
        )
    return RenderedBlock(blocks=blocks)


def render_solution(puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
    return RenderedBlock(blocks=[_block(puzzle, ctx, True, 1.0)])
