"""Word ladder: change one letter per step to climb from the first word to the last. Every rung is
a real English word. A small arrow under each rung shows WHICH letter changes, and the key rung
(boxed) is the answer (mystery keyword, `answer_is`).

The ladder is built from common words around the keyword. The independent check walks the whole
ENABLE dictionary with the same changing positions: exactly one ladder may fit.
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
from forge.wordlists import is_blocked
from forge.wordlists.dictionary import common_words, words

SOLVER = "wordladder-enable-dfs-v1"
MAX_ATTEMPTS = 600
HOW = (
    "Climb the ladder one rung at a time: change exactly one letter, the one marked with the "
    "arrow, to make a new English word. The boxed rung is your answer."
)


def _swap(w: str, i: int, ch: str) -> str:
    return w[:i] + ch + w[i + 1 :]


def _walk(start: str, steps: int, rng: Any, avoid: set[str]) -> tuple[list[str], list[int]] | None:
    """A random walk through common words, never changing the same position twice in a row."""
    pool = {w for w in common_words() if len(w) == len(start) and w.isalpha() and not is_blocked(w)}
    path, pos = [start], []
    for _ in range(steps):
        opts = [
            (i, _swap(path[-1], i, ch))
            for i in range(len(start))
            if not pos or i != pos[-1]
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if ch != path[-1][i]
        ]
        opts = [(i, w) for i, w in opts if w in pool and w not in path and w not in avoid]
        if not opts:
            return None
        i, w = rng.choice(opts)
        path.append(w)
        pos.append(i)
    return path, pos


def ladders(start: str, end: str, positions: list[int], limit: int = 2) -> list[list[str]]:
    """Every ladder start -> end over ENABLE words that changes these positions in this order."""
    vocab = words()
    out: list[list[str]] = []

    def rec(path: list[str], k: int) -> None:
        if len(out) >= limit:
            return
        if k == len(positions):
            if path[-1] == end:
                out.append(list(path))
            return
        i = positions[k]
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if ch == path[-1][i]:
                continue
            w = _swap(path[-1], i, ch)
            if w in vocab and w not in path:
                path.append(w)
                rec(path, k + 1)
                path.pop()

    rec([start], 0)
    return out


class WordLadder:
    name = "wordladder"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        ans = find_constraint(spec, AnswerIs)
        rng = make_rng(derive_seed(seed, "wordladder"))
        key = (ans.word if ans else str(spec.options.get("word") or "")).upper()
        if not key:
            key = rng.choice(sorted(w for w in common_words() if len(w) == 4 and w.isalpha()))
        if not (3 <= len(key) <= 5 and key.isalpha()):
            raise GenerationError("wordladder: the key word must be 3 to 5 letters")
        side = {"very_easy": 1, "easy": 2, "medium": 2, "hard": 3, "expert": 3}[spec.level]
        for attempt in range(MAX_ATTEMPTS):
            r2 = make_rng(derive_seed(seed, "wordladder", attempt))
            up = _walk(key, side, r2, set())
            if up is None:
                continue
            down = _walk(key, side, r2, set(up[0]))
            if down is None:
                continue
            path = list(reversed(up[0])) + down[0][1:]
            positions = list(reversed(up[1])) + down[1]
            if any(a == b for a, b in itertools.pairwise(positions)):
                continue
            if len(ladders(path[0], path[-1], positions, 2)) != 1:
                continue
            puzzle = build_puzzle(
                spec,
                seed,
                data={"start": path[0], "end": path[-1], "positions": positions, "key_rung": side},
                solution={"ladder": path, "word": key},
                token=key,
            )
            rep = self.verify(puzzle)
            if rep.ok:
                return puzzle.model_copy(
                    update={"verify": rep, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError(f"wordladder: no unique ladder through {key!r}")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        d = puzzle.data
        found = ladders(d["start"], d["end"], d["positions"], 2)
        if not found:
            return SolveResult(solved=False, solutions_found=0)
        lad = found[0]
        return SolveResult(
            solved=True,
            solution={"ladder": lad, "word": lad[int(d["key_rung"])]},
            solutions_found=len(found),
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        res = self.solve(puzzle)
        msgs: list[str] = []
        if res.solutions_found != 1:
            msgs.append(f"{res.solutions_found} ladders fit, expected exactly 1")
        if res.solution != puzzle.solution:
            msgs.append("solver ladder differs from the stored one")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.upper() != puzzle.solution["word"]:
            msgs.append("key rung differs from answer_is constraint")
        return VerifyReport(
            ok=not msgs, unique=res.solutions_found == 1, solver=SOLVER, messages=msgs
        )

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        steps = len(puzzle.data["positions"])
        score = round(min(85.0, 10 + steps * 11.0), 1)
        return DifficultyScore(
            score=score, label=level_from_score(score), features={"steps": float(steps)}
        )

    def _block(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool) -> dict[str, Any]:
        d = puzzle.data
        lad = puzzle.solution["ladder"]
        n = len(lad)
        rungs = [
            {
                "word": lad[k] if (solution or k in (0, n - 1)) else "",
                "change": d["positions"][k - 1] if k else None,
                "key": k == int(d["key_rung"]),
            }
            for k in range(n)
        ]
        cell = round(min(0.6, ctx.width_in / (len(lad[0]) + 4), ctx.height_in / (n * 1.6)), 3)
        return {"kind": "wordladder", "rungs": rungs, "letters": len(lad[0]), "cell_in": cell}

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[{"kind": "paragraph", "text": HOW}, self._block(puzzle, ctx, False)]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        w = puzzle.solution["word"]
        return RenderedBlock(
            blocks=[self._block(puzzle, ctx, True), {"kind": "paragraph", "text": f"Key rung: {w}"}]
        )


__all__ = ["Level", "WordLadder", "ladders"]
