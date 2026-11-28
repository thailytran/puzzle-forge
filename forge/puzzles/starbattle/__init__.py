"""Star Battle: place one star in every row, every column and every outlined region; stars never
touch, not even diagonally. Each cell carries a small letter; the letters under the stars, read
top to bottom, spell the answer (mystery keyword, `answer_is`).

Generator: a seeded star placement (one per row/column, no touching) -> regions grown from the stars
-> kept only when the independent backtracking solver finds exactly one solution.
"""

from __future__ import annotations

import string
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

SOLVER = "starbattle-backtrack-v1"
MAX_ATTEMPTS = 400
HOW = (
    "Place one star in every row, every column and every outlined region. Stars never touch, "
    "not even at a corner. Then read the letters under your stars from top to bottom."
)


def _stars(n: int, rng: Any) -> list[int] | None:
    """Column of the star in each row: a permutation with neighbours at least 2 apart."""
    cols: list[int] = []

    def rec() -> bool:
        if len(cols) == n:
            return True
        opts = [c for c in range(n) if c not in cols and (not cols or abs(c - cols[-1]) > 1)]
        rng.shuffle(opts)
        for c in opts:
            cols.append(c)
            if rec():
                return True
            cols.pop()
        return False

    return cols if rec() else None


def _regions(n: int, stars: list[int], rng: Any) -> list[list[int]]:
    """Grow one region from every star until the grid is covered (random flood fill)."""
    reg = [[-1] * n for _ in range(n)]
    front = []
    for r, c in enumerate(stars):
        reg[r][c] = r
        front.append((r, c))
    while front:
        i = rng.randrange(len(front))
        r, c = front[i]
        nb = [(r + dr, c + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        nb = [(a, b) for a, b in nb if 0 <= a < n and 0 <= b < n and reg[a][b] == -1]
        if not nb:
            front.pop(i)
            continue
        a, b = rng.choice(nb)
        reg[a][b] = reg[r][c]
        front.append((a, b))
    return reg


def _connected(reg: list[list[int]], rid: int) -> bool:
    cells = [(r, c) for r, row in enumerate(reg) for c, v in enumerate(row) if v == rid]
    if not cells:
        return False
    seen, stack = {cells[0]}, [cells[0]]
    while stack:
        r, c = stack.pop()
        for a, b in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if (a, b) not in seen and 0 <= a < len(reg) and 0 <= b < len(reg) and reg[a][b] == rid:
                seen.add((a, b))
                stack.append((a, b))
    return len(seen) == len(cells)


def _refine(reg: list[list[int]], stars: list[int], rng: Any, tries: int = 60) -> bool:
    """Move cells between regions until the true stars are the only solution."""
    n = len(reg)
    for _ in range(tries):
        k, first = count_solutions(reg, 2)
        alt = first if first != stars else _second(reg, stars)
        if k == 1 and first == stars:
            return True
        if alt is None:
            return False
        moves = [(r, c) for r, c in enumerate(alt) if c != stars[r]]
        rng.shuffle(moves)
        done = False
        for r, c in moves:  # give a wrong-star cell to a neighbouring region
            src = reg[r][c]
            nbs = {
                reg[a][b]
                for a, b in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1))
                if 0 <= a < n and 0 <= b < n and reg[a][b] != src
            }
            for dst in sorted(nbs, key=lambda _x: rng.random()):
                reg[r][c] = dst
                if _connected(reg, src):
                    done = True
                    break
                reg[r][c] = src
            if done:
                break
        if not done:
            return False
    return count_solutions(reg, 2) == (1, stars)


def _second(reg: list[list[int]], stars: list[int]) -> list[int] | None:
    """A solution other than `stars` (None when there is none)."""
    out: list[list[int]] = []
    _all(reg, out, 2)
    return next((s for s in out if s != stars), None)


def _all(reg: list[list[int]], out: list[list[int]], limit: int) -> None:
    n = len(reg)
    pick: list[int] = []

    def rec(r: int, cols: set[int], regs: set[int]) -> None:
        if len(out) >= limit:
            return
        if r == n:
            out.append(list(pick))
            return
        for c in range(n):
            if c in cols or reg[r][c] in regs or (pick and abs(c - pick[-1]) <= 1):
                continue
            pick.append(c)
            rec(r + 1, cols | {c}, regs | {reg[r][c]})
            pick.pop()

    rec(0, set(), set())


def count_solutions(reg: list[list[int]], limit: int = 2) -> tuple[int, list[int] | None]:
    """Backtracking row by row; returns (solutions found up to `limit`, first solution)."""
    n = len(reg)
    cols_used: set[int] = set()
    regs_used: set[int] = set()
    pick: list[int] = []
    found = 0
    first: list[int] | None = None

    def rec(r: int) -> None:
        nonlocal found, first
        if found >= limit:
            return
        if r == n:
            found += 1
            if first is None:
                first = list(pick)
            return
        for c in range(n):
            if c in cols_used or reg[r][c] in regs_used or (pick and abs(c - pick[-1]) <= 1):
                continue
            cols_used.add(c)
            regs_used.add(reg[r][c])
            pick.append(c)
            rec(r + 1)
            pick.pop()
            cols_used.discard(c)
            regs_used.discard(reg[r][c])

    rec(0)
    return found, first


class StarBattle:
    name = "starbattle"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        ans = find_constraint(spec, AnswerIs)
        word = (ans.word if ans else str(spec.options.get("word") or "")).upper()
        n = (
            len(word)
            if word
            else int(spec.options.get("size") or (6 if spec.audience.startswith("kids") else 8))
        )
        if not 5 <= n <= 10 or (word and not word.isalpha()):
            raise GenerationError("starbattle: the answer must be 5 to 10 letters")
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "starbattle", attempt))
            stars = _stars(n, rng)
            if stars is None:
                continue
            reg = _regions(n, stars, rng)
            if not _refine(reg, stars, rng):
                continue
            letters = [[rng.choice(string.ascii_uppercase) for _ in range(n)] for _ in range(n)]
            target = word or "".join(rng.choice(string.ascii_uppercase) for _ in range(n))
            for r, c in enumerate(stars):
                letters[r][c] = target[r]
            puzzle = build_puzzle(
                spec,
                seed,
                data={"size": n, "regions": reg, "letters": letters},
                solution={"stars": stars, "word": target},
                token=target,
            )
            rep = self.verify(puzzle)
            if rep.ok:
                return puzzle.model_copy(
                    update={"verify": rep, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError(f"starbattle: no unique {n}x{n} grid for {spec}")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        reg = puzzle.data["regions"]
        k, sol = count_solutions(reg)
        if sol is None:
            return SolveResult(solved=False, solutions_found=0)
        word = "".join(puzzle.data["letters"][r][c] for r, c in enumerate(sol))
        return SolveResult(solved=True, solution={"stars": sol, "word": word}, solutions_found=k)

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        n = int(puzzle.data["size"])
        msgs: list[str] = []
        if len({v for row in puzzle.data["regions"] for v in row}) != n:
            msgs.append("needs exactly n regions")
        res = self.solve(puzzle)
        if res.solutions_found != 1:
            msgs.append(f"{res.solutions_found} solutions, expected exactly 1")
        if res.solution is None or res.solution != puzzle.solution:
            msgs.append("solver answer differs from the stored one")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.upper() != puzzle.solution["word"]:
            msgs.append("word differs from answer_is constraint")
        return VerifyReport(
            ok=not msgs, unique=res.solutions_found == 1, solver=SOLVER, messages=msgs
        )

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        n = int(puzzle.data["size"])
        score = round(min(90.0, 15 + (n - 5) * 12.0), 1)
        return DifficultyScore(
            score=score, label=level_from_score(score), features={"size": float(n)}
        )

    def _block(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool) -> dict[str, Any]:
        n = int(puzzle.data["size"])
        cell = round(min(ctx.width_in / n, ctx.height_in / n, 0.7), 3)
        return {
            "kind": "starbattle",
            "regions": puzzle.data["regions"],
            "letters": puzzle.data["letters"],
            "stars": puzzle.solution["stars"] if solution else None,
            "cell_in": cell,
            "font_pt": round(cell * 72 * 0.3, 1),
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[{"kind": "paragraph", "text": HOW}, self._block(puzzle, ctx, False)]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        w = puzzle.solution["word"]
        return RenderedBlock(
            blocks=[self._block(puzzle, ctx, True), {"kind": "paragraph", "text": f"Word: {w}"}]
        )


__all__ = ["Level", "StarBattle", "count_solutions"]
