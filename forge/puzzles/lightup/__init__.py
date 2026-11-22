"""Light Up: place lanterns in white squares so every white square is lit. A lantern lights its row
and column until a black wall; two lanterns may never light each other; a numbered wall touches
exactly that many lanterns (sides only). Mystery use: the number of lanterns is the code
(`answer_is "9"`), or the letters under the lanterns spell a word (option `letters`).

Generator: seeded symmetric walls -> a full greedy lantern placement -> numbers on the walls ->
numbers removed one by one while the independent solver still finds exactly one solution.
"""

from __future__ import annotations

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

SOLVER = "lightup-backtrack-v1"
WALL = "#"  # unnumbered wall; "0".."4" numbered wall; "." white
MAX_ATTEMPTS = 300
HOW = (
    "Place lanterns in white squares so that every white square is lit. A lantern shines along "
    "its row and column until a black wall. No lantern may shine on another. A number on a wall "
    "tells how many lanterns touch it (above, below, left, right)."
)

Grid = list[list[str]]
Cell = tuple[int, int]


def _seen(g: Grid, r: int, c: int) -> list[Cell]:
    """White cells a lantern at (r, c) lights (itself included)."""
    n, m = len(g), len(g[0])
    out = [(r, c)]
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        a, b = r + dr, c + dc
        while 0 <= a < n and 0 <= b < m and g[a][b] == ".":
            out.append((a, b))
            a, b = a + dr, b + dc
    return out


def _nbrs(g: Grid, r: int, c: int) -> list[Cell]:
    return [
        (a, b)
        for a, b in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1))
        if 0 <= a < len(g) and 0 <= b < len(g[0])
    ]


def solve_all(g: Grid, limit: int = 2) -> list[set[Cell]]:
    """Every lantern set (up to `limit`) that solves the grid. Backtracking on the first dark
    cell: one of the cells that can see it must hold a lantern."""
    whites = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == "."]
    walls = [(r, c, int(v)) for r, row in enumerate(g) for c, v in enumerate(row) if v.isdigit()]
    sees = {w: _seen(g, *w) for w in whites}
    out: list[set[Cell]] = []
    lamps: set[Cell] = set()
    banned: set[Cell] = set()

    def lit_by(cell: Cell) -> bool:
        return any(x in lamps for x in sees[cell])

    def walls_ok(final: bool) -> bool:
        for r, c, k in walls:
            nb = [x for x in _nbrs(g, r, c) if g[x[0]][x[1]] == "."]
            have = sum(1 for x in nb if x in lamps)
            free = sum(1 for x in nb if x not in lamps and x not in banned and not lit_by(x))
            if have > k or have + free < k or (final and have != k):
                return False
        return True

    def rec() -> None:
        if len(out) >= limit:
            return
        dark = next((w for w in whites if not lit_by(w)), None)
        if dark is None:
            if walls_ok(True):
                out.append(set(lamps))
            return
        added: list[Cell] = []
        for cand in sees[dark]:
            if cand in banned or lit_by(cand):
                continue
            lamps.add(cand)
            if walls_ok(False):
                rec()
            lamps.discard(cand)
            banned.add(cand)  # this branch is done: later branches do without it
            added.append(cand)
            if len(out) >= limit:
                break
        for cand in added:
            banned.discard(cand)

    rec()
    return out


def _walls(n: int, rng: Any, share: float) -> Grid:
    g = [["." for _ in range(n)] for _ in range(n)]
    for r in range(n):
        for c in range(n):
            if (r, c) <= (n - 1 - r, n - 1 - c) and rng.random() < share:
                g[r][c] = g[n - 1 - r][n - 1 - c] = WALL
    return g


def _greedy(g: Grid, rng: Any) -> set[Cell]:
    whites = [(r, c) for r, row in enumerate(g) for c, v in enumerate(row) if v == "."]
    rng.shuffle(whites)
    lamps: set[Cell] = set()
    lit: set[Cell] = set()
    for w in whites:
        if w not in lit:
            lamps.add(w)
            lit.update(_seen(g, *w))
    return lamps


class LightUp:
    name = "lightup"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        ans = find_constraint(spec, AnswerIs)
        want = int(ans.word) if ans and ans.word.isdigit() else None
        n = int(spec.options.get("size") or (6 if spec.audience.startswith("kids") else 8))
        share = {"very_easy": 0.32, "easy": 0.3, "medium": 0.28, "hard": 0.25, "expert": 0.22}[
            spec.level
        ]
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "lightup", attempt))
            g = _walls(n, rng, share)
            lamps = _greedy(g, rng)
            if want is not None and len(lamps) != want:
                continue
            walls = [(r, c) for r in range(n) for c in range(n) if g[r][c] == WALL]
            for r, c in walls:  # number every wall, then thin the numbers out
                g[r][c] = str(sum(1 for x in _nbrs(g, r, c) if x in lamps))
            if len(solve_all(g)) != 1:
                continue
            rng.shuffle(walls)
            for r, c in walls:
                keep = g[r][c]
                g[r][c] = WALL
                if len(solve_all(g)) != 1:
                    g[r][c] = keep
            code = str(len(lamps))
            puzzle = build_puzzle(
                spec,
                seed,
                data={"size": n, "grid": ["".join(row) for row in g]},
                solution={"lamps": sorted([list(x) for x in lamps]), "code": code},
                token=code,
            )
            rep = self.verify(puzzle)
            if rep.ok:
                return puzzle.model_copy(
                    update={"verify": rep, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError(f"lightup: no unique grid for {spec}")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        g = [list(row) for row in puzzle.data["grid"]]
        sols = solve_all(g, 2)
        if not sols:
            return SolveResult(solved=False, solutions_found=0)
        lamps = sorted([list(x) for x in sols[0]])
        return SolveResult(
            solved=True,
            solution={"lamps": lamps, "code": str(len(lamps))},
            solutions_found=len(sols),
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        res = self.solve(puzzle)
        msgs: list[str] = []
        if res.solutions_found != 1:
            msgs.append(f"{res.solutions_found} solutions, expected exactly 1")
        if res.solution != puzzle.solution:
            msgs.append("solver answer differs from the stored one")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word != puzzle.solution["code"]:
            msgs.append("lantern count differs from answer_is constraint")
        return VerifyReport(
            ok=not msgs, unique=res.solutions_found == 1, solver=SOLVER, messages=msgs
        )

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        g = puzzle.data["grid"]
        n = len(g)
        numbers = sum(1 for row in g for v in row if v.isdigit())
        walls = sum(1 for row in g for v in row if v != ".")
        hint = numbers / max(1, walls)
        score = round(min(90.0, 10 + (n - 5) * 8 + (1 - hint) * 35), 1)
        return DifficultyScore(
            score=score, label=level_from_score(score), features={"numbered_share": hint}
        )

    def _block(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool) -> dict[str, Any]:
        n = int(puzzle.data["size"])
        cell = round(min(ctx.width_in / n, ctx.height_in / n, 0.7), 3)
        return {
            "kind": "lightup",
            "grid": puzzle.data["grid"],
            "lamps": puzzle.solution["lamps"] if solution else None,
            "cell_in": cell,
            "font_pt": round(cell * 72 * 0.5, 1),
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[{"kind": "paragraph", "text": HOW}, self._block(puzzle, ctx, False)]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        code = puzzle.solution["code"]
        return RenderedBlock(
            blocks=[
                self._block(puzzle, ctx, True),
                {"kind": "paragraph", "text": f"Lanterns: {code}"},
            ]
        )


__all__ = ["Level", "LightUp", "solve_all"]
