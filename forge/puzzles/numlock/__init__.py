"""Number lock: each dial is a chain of sums done left to right; the results are the digits of a
code. The generator builds every chain backwards from the wanted digit; the solver only walks the
printed chain forwards, so it shares no state with the generator. One answer by construction."""

from __future__ import annotations

import itertools
import random
from typing import Any

from forge.core.models import (
    AnswerIs,
    DifficultyScore,
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

SOLVER = "numlock-forward-v1"
STEPS = {"very_easy": 2, "easy": 2, "medium": 3, "hard": 4, "expert": 5}
SIGNS = {"+": "+", "-": "\u2212", "x": "\u00d7", "/": "\u00f7"}
MAX_VALUE = 200


def _kids(audience: str) -> bool:
    return audience in ("kids_6_8", "kids_9_12")


def _chain(digit: int, n_steps: int, kids: bool, rng: random.Random) -> dict[str, Any]:
    """Start number + steps whose left-to-right result is `digit` (built backwards)."""
    limit = 30 if kids else MAX_VALUE
    for _ in range(600):
        value = digit
        steps: list[list[Any]] = []
        for k in range(n_steps):
            # choose the forward operation of this step, then undo it to get the value before
            ops = ["+", "-"] if kids else ["+", "-", "x", "/"]
            if k == 0 and not kids and digit <= 9:
                ops = ["-", "/", "+"]  # last forward step: avoid "x" ending in a digit too often
            op = rng.choice(ops)
            if op == "+":
                n = rng.randint(1, max(1, min(value, 12)))
                before = value - n
            elif op == "-":
                n = rng.randint(2, 15)
                before = value + n
            elif op == "x":
                divs = [d for d in (2, 3, 4, 5, 6) if value and value % d == 0]
                if not divs:
                    continue
                n = rng.choice(divs)
                before = value // n
            else:
                n = rng.choice((2, 3, 4, 5))
                before = value * n
            if not 0 <= before <= limit:
                continue
            steps.append([op, n])
            value = before
        fwd = steps[::-1]
        inverse = {"+": "-", "-": "+", "x": "/", "/": "x"}
        dull = any(
            inverse[a[0]] == b[0] and a[1] == b[1] for a, b in itertools.pairwise(fwd)
        ) or len({op for op, _ in fwd}) < min(2, n_steps)
        if len(steps) == n_steps and value >= 2 and not dull:
            return {"start": value, "steps": fwd}
    raise GenerationError(f"numlock: no chain for digit {digit}")


def run(dial: dict[str, Any]) -> int | None:
    """Walk a dial forwards. None when a step leaves the whole numbers or goes below zero."""
    v = int(dial["start"])
    for op, n in dial["steps"]:
        n = int(n)
        if op == "+":
            v += n
        elif op == "-":
            v -= n
        elif op == "x":
            v *= n
        elif op == "/":
            if n == 0 or v % n:
                return None
            v //= n
        else:
            return None
        if v < 0:
            return None
    return v


def show(dial: dict[str, Any]) -> str:
    """Steps as a chain of arrows, so nobody applies "x before +" by mistake."""
    return "  \u2192  ".join([str(dial["start"]), *(f"{SIGNS[op]}{n}" for op, n in dial["steps"])])


class NumLock:
    name = "numlock"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        rng = make_rng(derive_seed(seed, "numlock"))
        ans = find_constraint(spec, AnswerIs)
        code = ans.word.strip() if ans else "".join(str(rng.randint(0, 9)) for _ in range(3))
        if not code.isdigit() or not 1 <= len(code) <= 6:
            raise GenerationError(f"numlock: code {code!r} must be 1-6 digits")
        kids = _kids(spec.audience)
        n = min(STEPS.get(spec.level, 3), 2 if kids else 5)
        dials = [_chain(int(d), n, kids, rng) for d in code]
        puzzle = build_puzzle(
            spec, seed, data={"dials": dials}, solution={"code": code}, token=code
        )
        rep = self.verify(puzzle)
        if not rep.ok:
            raise GenerationError(f"numlock failed verification: {rep.messages}")
        return puzzle.model_copy(update={"verify": rep, "difficulty": self.difficulty(puzzle)})

    def solve(self, puzzle: Puzzle) -> SolveResult:
        vals = [run(d) for d in puzzle.data["dials"]]
        ok = all(v is not None and 0 <= v <= 9 for v in vals)
        code = "".join(str(v) for v in vals) if ok else None
        return SolveResult(
            solved=ok, solution={"code": code} if ok else None, solutions_found=1 if ok else 0
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        res = self.solve(puzzle)
        if not res.solved or res.solution is None:
            msgs.append("a dial does not end in one digit")
        elif res.solution["code"] != puzzle.solution["code"]:
            msgs.append(f"dials give {res.solution['code']}, stored {puzzle.solution['code']}")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.strip() != puzzle.solution["code"]:
            msgs.append("code differs from the answer_is constraint")
        for i, d in enumerate(puzzle.data["dials"], 1):
            if not d["steps"]:
                msgs.append(f"dial {i} has no sums (the digit would be printed)")
        return VerifyReport(ok=not msgs, unique=not msgs, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        dials = puzzle.data["dials"]
        steps = sum(len(d["steps"]) for d in dials) / len(dials)
        hard_ops = sum(op in ("x", "/") for d in dials for op, _ in d["steps"])
        score = min(100.0, 10 + 14 * steps + 3 * hard_ops)
        return DifficultyScore(
            score=round(score, 1),
            label=level_from_score(score),
            features={"steps": steps, "dials": float(len(dials)), "mul_div": float(hard_ops)},
        )

    def _rows(self, puzzle: Puzzle, solution: bool) -> list[dict[str, str]]:
        code = puzzle.solution["code"]
        return [
            {"left": f"Dial {i}:   {show(d)}   =", "right": code[i - 1] if solution else ""}
            for i, d in enumerate(puzzle.data["dials"], 1)
        ]

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        size = 18.0 if ctx.large_print else 15.0
        return RenderedBlock(
            blocks=[
                {
                    "kind": "paragraph",
                    "text": "Work out each dial from left to right, one step at a time. "
                    "Every dial ends on one digit. Read the digits from top to bottom.",
                },
                {"kind": "spacer", "height_in": 0.2},
                {
                    "kind": "answer_lines",
                    "rows": self._rows(puzzle, False),
                    "font_pt": size,
                    "pairs": 1,
                    "gap_em": 2.2,
                },
            ]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[
                {
                    "kind": "answer_lines",
                    "rows": self._rows(puzzle, True),
                    "font_pt": 11.0,
                    "pairs": 1,
                },
                {"kind": "paragraph", "text": f"Code: {puzzle.solution['code']}"},
            ]
        )
