"""Nonogram (picture logic): shade cells so every row / column matches its run lengths.

Pictures are the 13 x 13 evidence icons (`forge.puzzles.cbn.font.ICONS`), so in a mystery the
finished grid shows the evidence object (`answer_is "@lantern"`). The generator only computes the
clues; the solver is a line solver (every placement of the runs on a line, intersected, until
nothing changes). A grid the line solver finishes alone has exactly one solution. When it gets
stuck, the generator reveals a few cells of the picture as givens (seeded) until it can finish.
"""

from __future__ import annotations

import itertools
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
from forge.puzzles.cbn.font import ICONS

SOLVER = "nonogram-line-solver-v1"
HOW = (
    "Shade the squares: the numbers give the runs of shaded squares in each row and "
    "column, in order. Dots are squares that stay empty. A picture appears."
)
UNKNOWN, EMPTY, FILLED = -1, 0, 1
Line = list[int]


def runs(line: list[int]) -> list[int]:
    """Run lengths of filled cells ([0] for an empty line)."""
    out = [len(list(g)) for v, g in itertools.groupby(line) if v == FILLED]
    return out or [0]


def _placements(clue: list[int], n: int) -> list[Line]:
    """Every line of length n that has exactly these runs."""
    if clue == [0]:
        return [[EMPTY] * n]
    out: list[Line] = []

    def rec(i: int, pos: int, acc: Line) -> None:
        if i == len(clue):
            out.append(acc + [EMPTY] * (n - len(acc)))
            return
        rest = sum(clue[i + 1 :]) + len(clue) - i - 1
        for start in range(pos, n - rest - clue[i] + 1):
            seg = [EMPTY] * (start - len(acc)) + [FILLED] * clue[i]
            nxt = acc + seg
            if i + 1 < len(clue):
                nxt = [*nxt, EMPTY]
            rec(i + 1, len(nxt), nxt)

    rec(0, 0, [])
    return out


def _fit(line: Line, clue: list[int]) -> Line | None:
    """Cells every consistent placement agrees on (None = contradiction)."""
    ok = [
        p
        for p in _placements(clue, len(line))
        if all(k in (UNKNOWN, v) for k, v in zip(line, p, strict=True))
    ]
    if not ok:
        return None
    return [ok[0][i] if all(p[i] == ok[0][i] for p in ok) else UNKNOWN for i in range(len(line))]


def line_solve(
    rows: list[list[int]], cols: list[list[int]], givens: list[list[int]]
) -> list[list[int]] | None:
    """Grid after line logic (UNKNOWN where undecided); None when the clues contradict."""
    h, w = len(rows), len(cols)
    g = [[UNKNOWN] * w for _ in range(h)]
    for r, c, v in givens:
        g[r][c] = v
    changed = True
    while changed:
        changed = False
        for r in range(h):
            new = _fit(g[r], rows[r])
            if new is None:
                return None
            if new != g[r]:
                g[r], changed = new, True
        for c in range(w):
            col = [g[r][c] for r in range(h)]
            new = _fit(col, cols[c])
            if new is None:
                return None
            if new != col:
                for r in range(h):
                    g[r][c] = new[r]
                changed = True
    return g


def picture_of(code: str) -> list[list[int]]:
    name = code.lstrip("@").lower()
    if name not in ICONS:
        raise GenerationError(f"nonogram: no picture {name!r} (known: {', '.join(ICONS)})")
    return [[int(ch) for ch in row] for row in ICONS[name]]


class Nonogram:
    name = "nonogram"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        ans = find_constraint(spec, AnswerIs)
        rng = make_rng(derive_seed(seed, "nonogram"))
        code = (
            ans.word if ans else "@" + str(spec.options.get("picture") or rng.choice(sorted(ICONS)))
        )
        pic = picture_of(code)
        rows = [runs(r) for r in pic]
        cols = [runs([pic[r][c] for r in range(len(pic))]) for c in range(len(pic[0]))]
        givens: list[list[int]] = []
        cells = [(r, c) for r in range(len(pic)) for c in range(len(pic[0]))]
        rng.shuffle(cells)
        while True:  # reveal cells until line logic alone finishes the picture
            g = line_solve(rows, cols, givens)
            if g is not None and all(v != UNKNOWN for row in g for v in row):
                break
            r, c = next(x for x in cells if g is None or g[x[0]][x[1]] == UNKNOWN)
            cells.remove((r, c))
            givens.append([r, c, pic[r][c]])
        puzzle = build_puzzle(
            spec,
            seed,
            data={"rows": rows, "cols": cols, "givens": givens, "h": len(rows), "w": len(cols)},
            solution={"grid": pic, "code": code.lower()},
            token=code.lower(),
        )
        rep = self.verify(puzzle)
        if not rep.ok:
            raise GenerationError(f"nonogram failed verification: {rep.messages}")
        return puzzle.model_copy(update={"verify": rep, "difficulty": self.difficulty(puzzle)})

    def solve(self, puzzle: Puzzle) -> SolveResult:
        d = puzzle.data
        g = line_solve(d["rows"], d["cols"], d["givens"])
        if g is None or any(v == UNKNOWN for row in g for v in row):
            return SolveResult(solved=False, solutions_found=0 if g is None else 2)
        name = next(
            (n for n, rows in ICONS.items() if [[int(x) for x in r] for r in rows] == g), None
        )
        return SolveResult(
            solved=True,
            solution={"grid": g, "code": "@" + name if name else "?"},
            solutions_found=1,
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        res = self.solve(puzzle)
        msgs: list[str] = []
        if not res.solved or res.solution is None:
            msgs.append("line logic does not finish the grid (not provably unique)")
        else:
            if res.solution["grid"] != puzzle.solution["grid"]:
                msgs.append("solved grid differs from the stored picture")
            if res.solution["code"] != puzzle.solution["code"]:
                msgs.append(f"picture reads {res.solution['code']!r}")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.lower() != puzzle.solution["code"]:
            msgs.append("picture differs from answer_is constraint")
        return VerifyReport(ok=not msgs, unique=res.solved, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        d = puzzle.data
        cells = d["h"] * d["w"]
        given = len(d["givens"]) / cells
        score = round(max(5.0, min(90.0, 20 + cells / 169 * 40 - given * 100)), 1)
        return DifficultyScore(
            score=score, label=level_from_score(score), features={"given_share": given}
        )

    def _block(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool) -> dict[str, Any]:
        d = puzzle.data
        rmax = max(len(r) for r in d["rows"])
        cmax = max(len(c) for c in d["cols"])
        cell = round(
            min(
                ctx.width_in / (d["w"] + rmax * 0.62), ctx.height_in / (d["h"] + cmax * 0.62), 0.45
            ),
            3,
        )
        return {
            "kind": "nonogram",
            "rows": d["rows"],
            "cols": d["cols"],
            "givens": d["givens"],
            "grid": puzzle.solution["grid"] if solution else None,
            "cell_in": cell,
            "font_pt": round(cell * 72 * 0.5, 1),
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[
                {
                    "kind": "paragraph",
                    "text": HOW,
                },
                self._block(puzzle, ctx, False),
            ]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        code = puzzle.solution["code"]
        return RenderedBlock(
            blocks=[
                self._block(puzzle, ctx, True),
                {"kind": "paragraph", "text": f"Picture: {code[1:]}"},
            ]
        )


__all__ = ["Level", "Nonogram", "line_solve", "runs"]
