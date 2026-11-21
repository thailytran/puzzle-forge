"""Maze → SVG (walls drawn in Python) + `maze` layout block (letters overlaid by Typst)."""

from __future__ import annotations

from typing import Any

from forge.core.models import Puzzle
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.puzzles.maze.grid import Cells, E, S


def _walls_path(cells: Cells) -> str:
    rows, cols = len(cells), len(cells[0])
    segs: list[str] = []
    # top border with entrance gap over (0,0); left border
    segs.append(f"M1 0H{cols}")
    segs.append(f"M0 0V{rows}")
    for r in range(rows):
        run_start: int | None = None
        for c in range(cols + 1):  # horizontal walls under row r (merged runs)
            closed = c < cols and not (cells[r][c] & S and r + 1 < rows)
            if r == rows - 1 and c == cols - 1:
                closed = False  # exit gap
            if closed and run_start is None:
                run_start = c
            elif not closed and run_start is not None:
                segs.append(f"M{run_start} {r + 1}H{c}")
                run_start = None
    for c in range(cols):
        run_start = None
        for r in range(rows + 1):  # vertical walls right of column c
            closed = r < rows and not (cells[r][c] & E and c + 1 < cols)
            if closed and run_start is None:
                run_start = r
            elif not closed and run_start is not None:
                segs.append(f"M{c + 1} {run_start}V{r}")
                run_start = None
    return "".join(segs)


def svg(puzzle: Puzzle, with_route: bool) -> bytes:
    cells: Cells = puzzle.data["cells"]
    rows, cols = len(cells), len(cells[0])
    pad = 0.6
    stroke = 0.12 if cols <= 20 else 0.16
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {cols + 2 * pad} '
        f'{rows + 2 * pad}">'
    ]
    if with_route:
        pts = [(0.5, -pad)] + [(c + 0.5, r + 0.5) for r, c in puzzle.solution["path"]]
        pts.append((cols - 0.5, rows + pad))
        coords = " ".join(f"{x:g},{y:g}" for x, y in pts)
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="#9a9a9a" stroke-width="0.38" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
    parts.append(
        f'<path d="{_walls_path(cells)}" fill="none" stroke="#000" stroke-width="{stroke}" '
        'stroke-linecap="square"/>'
    )
    parts.append("</svg>")
    return "".join(parts).encode()


def _block(puzzle: Puzzle, ctx: RenderCtx, with_route: bool, share: float) -> RenderedBlock:
    cells: Cells = puzzle.data["cells"]
    rows, cols = len(cells), len(cells[0])
    pad = 0.6
    width = min(ctx.width_in, ctx.height_in * share * (cols + 2 * pad) / (rows + 2 * pad))
    cell_in = width / (cols + 2 * pad)
    path = f"img/{puzzle.id}{'-sol' if with_route else ''}.svg"
    block: dict[str, Any] = {
        "kind": "maze",
        "path": path,
        "width_in": round(width, 3),
        "rows": rows,
        "cols": cols,
        "pad": pad,
        "letters": puzzle.data.get("letters", []),
        "font_pt": round(min(cell_in * 72 * 0.6, 20), 1),
    }
    return RenderedBlock(blocks=[block], files={path: svg(puzzle, with_route)})


def render(puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
    rb = _block(puzzle, ctx, False, 0.85)
    if puzzle.data.get("letters"):
        rb.blocks.append(
            {
                "kind": "paragraph",
                "text": "Collect the letters you pass on the way out, in order. "
                "They spell the answer.",
            }
        )
    return rb


def render_solution(puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
    return _block(puzzle, ctx, True, 1.0)
