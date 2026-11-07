"""Colour-by-number reveal, level 1: code-generated square mosaic with an embedded code glyph.

Type A "colour reveal": each cell shows a colour number. Type B "colour by answer": each cell
shows a mini sum whose answer selects the colour. Colouring every cell reveals the code
(digits/letters) in the darkest colour. Engine kept free of book/layout imports (reusable by
HALOSPARK's colour-by-number line).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from forge.core.models import (
    AnswerIs,
    DifficultyScore,
    Level,
    Puzzle,
    PuzzleSpec,
    SolveResult,
    VerifyReport,
    build_puzzle,
    level_from_score,
)
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.core.seeds import derive_seed, make_rng
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.cbn.font import GLYPHS, H, W, bitmap, match

SOLVER = "cbn-block-read-v1"
PALETTES: dict[str, list[tuple[str, str, int]]] = {  # (name, hex, answer for type B)
    "adult": [
        ("Navy", "#1f3a5f", 7),
        ("Sky", "#9cc9e8", 12),
        ("Sand", "#f2d49b", 15),
        ("Mint", "#b7e4c7", 18),
        ("Peach", "#f8c0a8", 24),
        ("Lilac", "#d7c4ec", 30),
    ],
    "kids": [
        ("Blue", "#2346a0", 4),
        ("Yellow", "#ffe066", 6),
        ("Green", "#9be39b", 8),
        ("Pink", "#ffb3c7", 10),
    ],
}
MIN_CONTRAST = 0.35  # luminance gap between the code colour and the lightest-dark background


@dataclass(frozen=True)
class CbnParams:
    rows: int
    cols: int
    mode: str  # "A" | "B"


def resolve_params(spec: PuzzleSpec) -> CbnParams:
    kids = spec.audience in ("kids_6_8", "kids_9_12")
    mode = str(spec.options.get("mode") or ("A" if spec.level in ("very_easy", "easy") else "B"))
    if mode == "A":
        size = 14 if kids else (20 if spec.level in ("very_easy", "easy") else 26)
    else:
        size = 10 if kids else 16
    return CbnParams(size, size, mode)


def palette(audience: str) -> list[tuple[str, str, int]]:
    return PALETTES["kids" if audience in ("kids_6_8", "kids_9_12") else "adult"]


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def glyph_layout(code: str, rows: int, cols: int) -> tuple[int, int, int]:
    """(scale, top, left) of the code inside the grid; scale = cells per font pixel."""
    width_px = len(code) * (W + 1) - 1
    s = min((cols - 2) // width_px, (rows - 2) // H)
    if s < 1:
        raise GenerationError(f"cbn: code {code!r} does not fit a {rows}x{cols} mosaic")
    return s, (rows - H * s) // 2, (cols - width_px * s) // 2


def paint(code: str, p: CbnParams, n_colors: int, rng: random.Random) -> list[list[int]]:
    """Colour index per cell (1 = code colour, 2..n = background rings with seeded texture)."""
    grid: list[list[int]] = []
    cr, cc = (p.rows - 1) / 2, (p.cols - 1) / 2
    band = max(2, min(p.rows, p.cols) // 7)
    for r in range(p.rows):
        row = []
        for c in range(p.cols):
            d = int(max(abs(r - cr), abs(c - cc)) // band)
            shift = 1 if rng.random() < 0.15 else 0
            row.append(2 + (d + shift) % (n_colors - 1))
        grid.append(row)
    s, top, left = glyph_layout(code, p.rows, p.cols)
    for k, ch in enumerate(code):
        bm = bitmap(ch)
        x0 = left + k * (W + 1) * s
        for gy in range(H):
            for gx in range(W):
                if bm[gy][gx]:
                    for dy in range(s):
                        for dx in range(s):
                            grid[top + gy * s + dy][x0 + gx * s + dx] = 1
    return grid


def _expr(target: int, kids: bool, rng: random.Random) -> str:
    ops = ["+"] if kids else ["+", "-", "x"]
    factors = [a for a in range(2, target) if target % a == 0 and target // a >= 2]
    op = rng.choice([o for o in ops if o != "x" or factors])
    if op == "+":
        a = rng.randint(1, target - 1)
        return f"{a}+{target - a}"
    if op == "-":
        b = rng.randint(1, 9)
        return f"{target + b}-{b}"
    a = rng.choice(factors)
    return f"{a}x{target // a}"


def eval_expr(e: str) -> int:
    """Evaluate a mini sum 'a+b', 'a-b' or 'axb' (no eval())."""
    for op in "+-x":
        if op in e:
            a, b = (int(x) for x in e.split(op))
            return a + b if op == "+" else a - b if op == "-" else a * b
    return int(e)


def read_with(colors: list[list[int]], sample: str = "majority", max_len: int = 4) -> str:
    """Read the revealed code: for each possible code length recompute the centred glyph frame
    (same geometry as the layout) and accept the length where every glyph matches exactly and no
    code-coloured cell lies outside the frame.
    `sample`: "majority" (s x s block vote) or "centre"."""
    rows, cols = len(colors), len(colors[0])
    dark = {(r, c) for r in range(rows) for c in range(cols) if colors[r][c] == 1}
    for n in range(1, max_len + 1):
        try:
            s, top, left = glyph_layout("0" * n, rows, cols)
        except GenerationError:
            break
        inside: set[tuple[int, int]] = set()
        out = []
        for k in range(n):
            x0 = left + k * (W + 1) * s
            block = []
            for gy in range(H):
                line = []
                for gx in range(W):
                    cells = [
                        (top + gy * s + dy, x0 + gx * s + dx) for dy in range(s) for dx in range(s)
                    ]
                    inside.update(cells)
                    if sample == "majority":
                        on = sum(cell in dark for cell in cells) * 2 > s * s
                    else:
                        on = (top + gy * s + s // 2, x0 + gx * s + s // 2) in dark
                    line.append(1 if on else 0)
                block.append(line)
            ch, err = match(block)
            out.append(ch if err == 0 else "?")
        if "?" not in out and dark <= inside:
            return "".join(out)
    return "?"


def read_code(colors: list[list[int]]) -> str:
    return read_with(colors, "majority")


class ColorByNumber:
    name = "cbn"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        p = resolve_params(spec)
        pal = palette(spec.audience)
        kids = spec.audience in ("kids_6_8", "kids_9_12")
        rng = make_rng(derive_seed(seed, "cbn"))
        ans = find_constraint(spec, AnswerIs)
        code = (ans.word if ans else str(spec.options.get("code") or rng.randint(10, 99))).upper()
        if any(ch not in GLYPHS for ch in code):
            raise GenerationError(f"cbn: unsupported characters in code {code!r}")
        if kids and len(code) > 1 and not ans:
            code = code[0]
        width_px = len(code) * (W + 1) - 1
        if p.cols < width_px + 2:  # widen the mosaic for long codes
            p = CbnParams(max(p.rows, H + 2), width_px + 2, p.mode)
        colors = paint(code, p, len(pal), rng)
        if p.mode == "A":
            cells: list[list[str]] = [[str(v) for v in row] for row in colors]
        else:
            cells = [[_expr(pal[v - 1][2], kids, rng) for v in row] for row in colors]
        puzzle = build_puzzle(
            spec,
            seed,
            data={
                "mode": p.mode,
                "rows": p.rows,
                "cols": p.cols,
                "cells": cells,
                "palette": [
                    {"n": i + 1, "name": n, "hex": h, "answer": a}
                    for i, (n, h, a) in enumerate(pal)
                ],
            },
            solution={"colors": colors, "code": code},
            token=code,
        )
        rep = self.verify(puzzle)
        if not rep.ok:
            raise GenerationError(f"cbn failed verification: {rep.messages}")
        return puzzle.model_copy(update={"verify": rep, "difficulty": self.difficulty(puzzle)})

    def colours_from_cells(self, puzzle: Puzzle) -> list[list[int]] | None:
        pal = puzzle.data["palette"]
        by_answer = {e["answer"]: e["n"] for e in pal}
        out = []
        for row in puzzle.data["cells"]:
            line = []
            for label in row:
                if puzzle.data["mode"] == "A":
                    v = int(label)
                    if not 1 <= v <= len(pal):
                        return None
                else:
                    v = by_answer.get(eval_expr(label), 0)
                    if not v:
                        return None
                line.append(v)
            out.append(line)
        return out

    def solve(self, puzzle: Puzzle) -> SolveResult:
        colors = self.colours_from_cells(puzzle)
        if colors is None:
            return SolveResult(solved=False)
        return SolveResult(
            solved=True, solution={"colors": colors, "code": read_code(colors)}, solutions_found=1
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        res = self.solve(puzzle)
        if not res.solved or res.solution is None:
            return VerifyReport(
                ok=False,
                unique=False,
                solver=SOLVER,
                messages=["a cell has no valid colour (number/answer)"],
            )
        if res.solution["colors"] != puzzle.solution["colors"]:
            msgs.append("colouring from the cells differs from the stored solution")
        if res.solution["code"] != puzzle.solution["code"]:
            msgs.append(
                f"revealed code reads {res.solution['code']!r}, expected "
                f"{puzzle.solution['code']!r}"
            )
        pal = puzzle.data["palette"]
        dark = _lum(pal[0]["hex"])
        lightest_bg = min(_lum(e["hex"]) for e in pal[1:])
        if lightest_bg - dark < MIN_CONTRAST:
            msgs.append("code colour does not contrast enough with the background colours")
        if len({e["answer"] for e in pal}) != len(pal):
            msgs.append("two colours share an answer value (type B ambiguous)")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.upper() != puzzle.solution["code"]:
            msgs.append("code differs from answer_is constraint")
        return VerifyReport(ok=not msgs, unique=True, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        cells = puzzle.data["rows"] * puzzle.data["cols"]
        b = puzzle.data["mode"] == "B"
        score = round(min(95.0, 8 + cells / 676 * 40 + (35 if b else 0)), 1)
        f = {
            "cells": float(cells),
            "type_b": float(b),
            "colours": float(len(puzzle.data["palette"])),
        }
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _block(
        self, puzzle: Puzzle, ctx: RenderCtx, solution: bool, share: float
    ) -> dict[str, Any]:
        rows, cols = puzzle.data["rows"], puzzle.data["cols"]
        cell = round(min(ctx.width_in / cols, ctx.height_in * share / rows, 0.6), 3)
        b = puzzle.data["mode"] == "B"
        font = cell * 72 * (0.28 if b else 0.45)
        if ctx.large_print:
            font = max(font, 16.0) if not b else font
        return {
            "kind": "cbn_grid",
            "cells": puzzle.data["cells"],
            "colors": puzzle.solution["colors"] if solution else None,
            "palette": puzzle.data["palette"],
            "mode": puzzle.data["mode"],
            "cell_in": cell,
            "font_pt": round(font, 1),
            "legend": not solution,
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        how = (
            "Colour each square with the colour of its number."
            if puzzle.data["mode"] == "A"
            else "Solve the sum in each square, then colour it with the colour of the answer."
        )
        return RenderedBlock(
            blocks=[
                {"kind": "paragraph", "text": how + " A secret code will appear."},
                self._block(puzzle, ctx, False, 0.78),
            ]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        blk = self._block(puzzle, ctx, True, 0.85)
        return RenderedBlock(
            blocks=[blk, {"kind": "paragraph", "text": f"Code: {puzzle.solution['code']}"}]
        )


__all__ = ["ColorByNumber", "Level", "read_code"]
