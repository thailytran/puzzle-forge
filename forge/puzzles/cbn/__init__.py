"""Colour-by-number reveal, level 1: code-generated mosaic with an embedded code glyph.

Cell shapes: square (default, legacy layout), hexagon, triangle and circle (dots) — see
`tiling.py`. Every shape is verified the same way: the solution is painted to a raster and the
code is read back from the picture.

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
from forge.puzzles.cbn import tiling
from forge.puzzles.cbn.font import H, W, bitmap, is_icon, known, match
from forge.puzzles.cbn.pictures import PICTURE_H, PICTURE_PALETTE, PICTURE_W, PICTURES

SOLVER = "cbn-block-read-v1"
SOLVER_RASTER = "cbn-raster-read-v1"
SOLVER_PICTURE = "cbn-picture-match-v1"
# owner 2026-11-21: adult picture mosaics use ~4 mm cells so the picture is sharp
PICTURE_MIN_MM = 3.8
PICTURE_SHAPES = ("square", "circle")
# Smallest cell (inscribed-circle diameter, mm) a reader is asked to colour, and smallest label.
MIN_CELL_MM = {"kids_6_8": 8.0, "kids_9_12": 8.0}
MIN_CELL_MM_DEFAULT = 5.0
MIN_LABEL_PT = 6.0
PAGE_MM = (162.0, 158.0)  # mosaic area the cell count is planned for (fits Letter and A4)
MODE_B_MIN_MM = 7.2  # a mini sum needs a cell this big to stay at MIN_LABEL_PT
LEVEL_CELL_FACTOR = {"very_easy": 1.6, "easy": 1.35, "medium": 1.15, "hard": 1.0, "expert": 1.0}
MODE_B_SHAPES = ("square", "hex")  # shapes with room for a mini sum in every cell
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


def min_cell_mm(audience: str) -> float:
    return MIN_CELL_MM.get(audience, MIN_CELL_MM_DEFAULT)


def plan_tiling(shape: str, code: str, spec: PuzzleSpec, mode: str = "A") -> tiling.Tiling:
    """Largest-celled tiling of `shape` that fits the page and still holds the code.
    Cells never go below the audience minimum (and below MODE_B_MIN_MM for mini sums)."""
    base = max(min_cell_mm(spec.audience), MODE_B_MIN_MM if mode == "B" else 0.0)
    want = LEVEL_CELL_FACTOR.get(spec.level, 1.0)
    one = tiling.make(shape, 1, 1)
    dx = tiling.make(shape, 1, 2).width - one.width
    dy = tiling.make(shape, 2, 1).height - one.height
    last: GenerationError | None = None
    for factor in [f for f in (1.6, 1.35, 1.15, 1.0) if f <= want]:
        unit_mm = base * factor / one.min_dim
        cols = 1 + int((PAGE_MM[0] / unit_mm - one.width) / dx)
        rows = 1 + int((PAGE_MM[1] / unit_mm - one.height) / dy)
        try:
            t = tiling.make(shape, max(rows, 2), max(cols, 2))
            tiling.frame_of(code, t)
            return t
        except GenerationError as e:
            last = e
    raise GenerationError(
        f"cbn: code {code!r} does not fit {shape} cells of at least {base:g} mm ({last})"
    )


def paint_tiling(code: str, t: tiling.Tiling, n_colors: int, rng: random.Random) -> list[int]:
    """Colour index per cell of a tiling (1 = code colour, 2..n = background rings)."""
    on = tiling.code_cells(code, t)
    band = max(0.12, 1 / 7)
    out = []
    for cell, is_code in zip(t.cells, on, strict=True):
        d = int(max(abs(cell.cx / t.width - 0.5), abs(cell.cy / t.height - 0.5)) * 2 / band)
        shift = 1 if rng.random() < 0.15 else 0
        out.append(1 if is_code else 2 + (d + shift) % (n_colors - 1))
    return out


def tiling_of(puzzle: Puzzle) -> tiling.Tiling:
    """The tiling a puzzle was built on (square mosaics included)."""
    shape = puzzle.data.get("shape", "square")
    return tiling.make(shape, puzzle.data["rows"], puzzle.data["cols"])


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


def is_picture(code: str) -> bool:
    """A code "#lantern": the whole mosaic is a multi-colour picture from `pictures.py`."""
    return code.startswith("#")


def read_picture(colors: list[int], rows: int, cols: int) -> str:
    """Name the picture a finished colouring shows ("?" when it is none of the known ones).
    Independent of the generator: it only looks at the colours the reader ends up with."""
    if (cols, rows) != (PICTURE_W, PICTURE_H) or len(colors) != rows * cols:
        return "?"
    got = ["".join(str(v) for v in colors[r * cols : (r + 1) * cols]) for r in range(rows)]
    hits = [name for name, pic in PICTURES.items() if list(pic) == got]
    return "#" + hits[0] if len(hits) == 1 else "?"


class ColorByNumber:
    name = "cbn"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        p = resolve_params(spec)
        pal = palette(spec.audience)
        kids = spec.audience in ("kids_6_8", "kids_9_12")
        rng = make_rng(derive_seed(seed, "cbn"))
        ans = find_constraint(spec, AnswerIs)
        code = ans.word if ans else str(spec.options.get("code") or rng.randint(10, 99))
        code = code.lower() if is_icon(code) or is_picture(code) else code.upper()
        if is_picture(code):
            return self._generate_picture(spec, seed, code)
        if not known(code):
            raise GenerationError(f"cbn: unsupported characters in code {code!r}")
        if kids and len(code) > 1 and not ans and not is_icon(code):
            code = code[0]
        shape = str(spec.options.get("shape") or ("square" if is_icon(code) else ""))
        if shape:  # explicit shape (square included): planned tiling with the minimum cell size
            return self._generate_tiling(spec, seed, shape, code, p.mode, rng)
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

    def _generate_tiling(
        self, spec: PuzzleSpec, seed: int, shape: str, code: str, mode: str, rng: random.Random
    ) -> Puzzle:
        pal = palette(spec.audience)
        kids = spec.audience in ("kids_6_8", "kids_9_12")
        if mode == "B" and shape not in MODE_B_SHAPES:
            mode = "A"
        try:
            t = plan_tiling(shape, code, spec, mode)
        except GenerationError:
            if mode != "B":
                raise
            mode = "A"  # the sums need bigger cells than the code leaves room for
            t = plan_tiling(shape, code, spec, mode)
        colors = paint_tiling(code, t, len(pal), rng)
        if mode == "A":
            labels = [str(v) for v in colors]
        else:
            labels = [_expr(pal[v - 1][2], kids, rng) for v in colors]
        puzzle = build_puzzle(
            spec,
            seed,
            data={
                "mode": mode,
                "shape": shape,
                "rows": t.rows,
                "cols": t.cols,
                "cells": [labels],  # one row: cell order of the tiling
                "palette": [
                    {"n": i + 1, "name": n, "hex": h, "answer": a}
                    for i, (n, h, a) in enumerate(pal)
                ],
            },
            solution={"colors": [colors], "code": code},
            token=code,
        )
        rep = self.verify(puzzle)
        if not rep.ok:
            raise GenerationError(f"cbn failed verification: {rep.messages}")
        return puzzle.model_copy(update={"verify": rep, "difficulty": self.difficulty(puzzle)})

    def _generate_picture(self, spec: PuzzleSpec, seed: int, code: str) -> Puzzle:
        """Full-page picture mosaic: every cell carries the palette number of its pixel."""
        name = code[1:]
        if name not in PICTURES:
            raise GenerationError(f"cbn: no picture called {name!r} (known: {', '.join(PICTURES)})")
        shape = str(spec.options.get("shape") or "square")
        if shape not in PICTURE_SHAPES:
            shape = "square"  # pictures need a square lattice (squares or dots)
        colors = [int(ch) for row in PICTURES[name] for ch in row]
        puzzle = build_puzzle(
            spec,
            seed,
            data={
                "mode": "A",
                "art": True,
                "shape": shape,
                "rows": PICTURE_H,
                "cols": PICTURE_W,
                "cells": [[str(v) for v in colors]],
                "palette": [
                    {"n": i + 1, "name": n, "hex": h, "answer": i + 1}
                    for i, (n, h) in enumerate(PICTURE_PALETTE)
                ],
            },
            solution={"colors": [colors], "code": code},
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
        if puzzle.data.get("art"):
            code = read_picture(colors[0], puzzle.data["rows"], puzzle.data["cols"])
        elif "shape" in puzzle.data:
            code = tiling.read_raster(tiling_of(puzzle), colors[0])
        else:
            code = read_code(colors)
        return SolveResult(
            solved=True, solution={"colors": colors, "code": code}, solutions_found=1
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
        flat = [v for row in res.solution["colors"] for v in row]
        pal = puzzle.data["palette"]
        art = bool(puzzle.data.get("art"))
        if len(flat) != len(tiling_of(puzzle).cells):
            msgs.append("number of labelled cells differs from the tiling")
        elif art:
            if len({e["hex"].lower() for e in pal}) != len(pal):
                msgs.append("two palette numbers share a colour")
            if len(set(flat)) < 4:
                msgs.append("picture uses fewer than four colours")
        elif tiling.read_raster(tiling_of(puzzle), flat) != puzzle.solution["code"]:
            msgs.append("the painted picture does not show the code clearly (raster read)")
        if not art:
            dark = _lum(pal[0]["hex"])
            lightest_bg = min(_lum(e["hex"]) for e in pal[1:])
            if lightest_bg - dark < MIN_CONTRAST:
                msgs.append("code colour does not contrast enough with the background colours")
        if len({e["answer"] for e in pal}) != len(pal):
            msgs.append("two colours share an answer value (type B ambiguous)")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.upper() != str(puzzle.solution["code"]).upper():
            msgs.append("code differs from answer_is constraint")
        solver = SOLVER_PICTURE if art else SOLVER_RASTER if "shape" in puzzle.data else SOLVER
        return VerifyReport(ok=not msgs, unique=True, solver=solver, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        cells = sum(len(row) for row in puzzle.data["cells"])
        b = puzzle.data["mode"] == "B"
        shape_bonus = {"hex": 6, "circle": 3, "triangle": 12}.get(puzzle.data.get("shape", ""), 0)
        score = round(min(95.0, 8 + cells / 676 * 40 + (35 if b else 0) + shape_bonus), 1)
        f = {
            "cells": float(cells),
            "type_b": float(b),
            "colours": float(len(puzzle.data["palette"])),
        }
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _block(
        self, puzzle: Puzzle, ctx: RenderCtx, solution: bool, share: float
    ) -> dict[str, Any]:
        if "shape" in puzzle.data:
            return self._poly_block(puzzle, ctx, solution, share)
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
            "cell_mm": round(cell * 25.4, 2),
            "font_pt": round(font, 1),
            "legend": not solution,
        }

    def _poly_block(
        self, puzzle: Puzzle, ctx: RenderCtx, solution: bool, share: float
    ) -> dict[str, Any]:
        """Polygon mosaic: every cell is drawn from its outline, sizes in inches."""
        t = tiling_of(puzzle)
        cap = 0.6 / t.min_dim  # same upper cell size as square mosaics
        k = min(ctx.width_in / t.width, ctx.height_in * share / t.height, cap)
        b = puzzle.data["mode"] == "B"
        font = t.min_dim * k * 72 * (0.3 if b else 0.5)
        colors = puzzle.solution["colors"][0]
        labels = puzzle.data["cells"][0]
        return {
            "kind": "cbn_poly",
            "shape": t.shape,
            "w_in": round(t.width * k, 3),
            "h_in": round(t.height * k, 3),
            "cells": [
                {
                    "p": [[round(x * k, 4), round(y * k, 4)] for x, y in c.pts],
                    "c": [round(c.cx * k, 4), round(c.cy * k, 4)],
                    "l": lab,
                    "f": colors[i] if solution else 0,
                }
                for i, (c, lab) in enumerate(zip(t.cells, labels, strict=True))
            ],
            "palette": puzzle.data["palette"],
            "mode": puzzle.data["mode"],
            "cell_mm": round(t.min_dim * k * 25.4, 2),
            "min_mm": PICTURE_MIN_MM
            if puzzle.data.get("art") and not puzzle.spec.audience.startswith("kids")
            else min_cell_mm(puzzle.spec.audience),
            "label_in": round(t.min_dim * k, 4),
            "font_pt": round(font, 1),
            "legend": not solution,
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        cell = {"hex": "hexagon", "triangle": "triangle", "circle": "dot"}.get(
            puzzle.data.get("shape", "square"), "square"
        )
        code = str(puzzle.solution.get("code", ""))
        picture = is_icon(code) or is_picture(code)
        reveal = " A hidden picture will appear." if picture else " A secret code will appear."
        how = (
            f"Colour each {cell} with the colour of its number."
            if puzzle.data["mode"] == "A"
            else f"Solve the sum in each {cell}, then colour it with the colour of the answer."
        )
        return RenderedBlock(
            blocks=[
                {"kind": "paragraph", "text": how + reveal},
                self._block(puzzle, ctx, False, 1.0 if puzzle.data.get("art") else 0.78),
            ]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        blk = self._block(puzzle, ctx, True, 0.85)
        code = str(puzzle.solution["code"])
        shown = f"Picture: {code[1:]}" if is_icon(code) or is_picture(code) else f"Code: {code}"
        return RenderedBlock(blocks=[blk, {"kind": "paragraph", "text": shown}])


__all__ = [
    "ColorByNumber",
    "Level",
    "is_picture",
    "min_cell_mm",
    "read_code",
    "read_picture",
    "tiling_of",
]
