"""Wordoku: a sudoku written with the letters of one word; the shaded row spells that word.

Built on the sudoku generator (uniqueness checked there), then re-verified here by an independent
route: letters -> digits by alphabet order, solved with the pure-Python backtracking solver, the
grid must have exactly one solution and the shaded row must read the word.
Mystery use: the case forces the word (`answer_is`), so solving the grid yields the keyword.
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
from forge.puzzles.sudoku.grid import box_shape, count_solutions
from forge.puzzles.sudoku.grid import solve as py_solve

SOLVER = "wordoku-letters-to-digits-backtrack-v1"
DEFAULT_WORDS = {4: "STAR", 6: "WINTER", 9: "SNOWFLAKE"}
MAX_ATTEMPTS = 40


def size_of(spec: PuzzleSpec, word: str | None) -> int:
    if word:
        return len(word)
    n = int(spec.options.get("size") or 0)
    if n:
        return n
    if spec.audience == "kids_6_8":
        return 4 if spec.level in ("very_easy", "easy") else 6
    if spec.audience == "kids_9_12":
        return 6
    return 9


def word_ok(word: str) -> bool:
    """A wordoku word has 4, 6 or 9 letters, all different."""
    w = word.upper()
    return w.isalpha() and len(w) in (4, 6, 9) and len(set(w)) == len(w)


def _letters_to_digits(grid: list[list[str]], letters: list[str]) -> list[list[int]]:
    idx = {ch: i + 1 for i, ch in enumerate(letters)}
    return [[idx.get(ch, 0) for ch in row] for row in grid]


class Wordoku:
    name = "wordoku"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        from forge.puzzles.sudoku.generator import build  # rustoku for 9x9 uniqueness

        ans = find_constraint(spec, AnswerIs)
        word = (ans.word if ans else str(spec.options.get("word") or "")).upper()
        n = size_of(spec, word or None)
        word = word or DEFAULT_WORDS[n]
        if not word_ok(word) or len(word) != n:
            raise GenerationError(f"wordoku: {word!r} needs {n} different letters (4, 6 or 9)")
        sd_spec = spec.model_copy(
            update={"type": "sudoku", "constraints": [], "options": {"size": n}}
        )
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "wordoku", attempt))
            built = build(sd_spec, rng)
            if built is None:
                continue
            givens, solution, _level = built
            row = rng.randrange(n)
            to_letter = {
                solution[row][c]: word[c] for c in range(n)
            }  # the shaded row spells the word
            g = [[to_letter[v] if v else "" for v in r] for r in givens]
            s = [[to_letter[v] for v in r] for r in solution]
            puzzle = build_puzzle(
                spec,
                seed,
                data={"size": n, "givens": g, "letters": sorted(word), "row": row},
                solution={"grid": s, "word": word},
                token=word,
            )
            rep = self.verify(puzzle)
            if rep.ok:
                return puzzle.model_copy(
                    update={"verify": rep, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError(f"wordoku: no valid grid for {spec}")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        letters = list(puzzle.data["letters"])
        digits = _letters_to_digits(puzzle.data["givens"], letters)
        found = count_solutions([list(r) for r in digits], 2)
        sol = py_solve([list(r) for r in digits])
        if sol is None:
            return SolveResult(solved=False, solutions_found=found)
        grid = [[letters[v - 1] for v in r] for r in sol]
        word = "".join(grid[int(puzzle.data["row"])])
        return SolveResult(
            solved=True, solution={"grid": grid, "word": word}, solutions_found=found
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        n = int(puzzle.data["size"])
        try:
            box_shape(n)
        except ValueError as e:
            return VerifyReport(ok=False, unique=False, solver=SOLVER, messages=[str(e)])
        if len(set(puzzle.data["letters"])) != n:
            msgs.append("the letter set must hold n different letters")
        res = self.solve(puzzle)
        if res.solutions_found != 1:
            msgs.append(f"grid has {res.solutions_found} solutions, expected exactly 1")
        if not res.solved or res.solution is None:
            msgs.append("grid cannot be solved")
        else:
            if res.solution["grid"] != puzzle.solution["grid"]:
                msgs.append("solver solution differs from the stored one")
            if res.solution["word"] != puzzle.solution["word"]:
                got, want = res.solution["word"], puzzle.solution["word"]
                msgs.append(f"shaded row reads {got!r}, expected {want!r}")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and ans.word.upper() != puzzle.solution["word"]:
            msgs.append("word differs from answer_is constraint")
        return VerifyReport(
            ok=not msgs, unique=res.solutions_found == 1, solver=SOLVER, messages=msgs
        )

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        n = int(puzzle.data["size"])
        blanks = sum(1 for r in puzzle.data["givens"] for v in r if not v)
        share = blanks / (n * n)
        score = round(min(95.0, {4: 10, 6: 25, 9: 45}[n] + share * 50), 1)
        return DifficultyScore(
            score=score, label=level_from_score(score), features={"blank_share": share}
        )

    def _block(
        self, puzzle: Puzzle, ctx: RenderCtx, solution: bool, share: float
    ) -> dict[str, Any]:
        n = int(puzzle.data["size"])
        br, bc = box_shape(n)
        g, s = puzzle.data["givens"], puzzle.solution["grid"]
        cell = round(min(ctx.width_in / n, ctx.height_in * share / n, 0.75), 3)
        return {
            "kind": "sudoku_grid",
            "size": n,
            "box_rows": br,
            "box_cols": bc,
            "cells": [
                [(s[r][c] if solution else g[r][c]) or None for c in range(n)] for r in range(n)
            ],
            "given_mask": [[bool(g[r][c]) for c in range(n)] for r in range(n)],
            "shaded": [[int(puzzle.data["row"]), c] for c in range(n)],
            "cell_in": cell,
            "font_pt": max(18.0, round(cell * 72 * 0.55, 1))
            if ctx.large_print
            else round(cell * 72 * 0.55, 1),
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        letters = " ".join(puzzle.data["letters"])
        return RenderedBlock(
            blocks=[
                {
                    "kind": "paragraph",
                    "text": "Fill the grid so every row, column and box holds each of these "
                    f"letters once: "
                    f"{letters}. The shaded row spells the answer.",
                },
                self._block(puzzle, ctx, False, 0.8),
            ]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[
                self._block(puzzle, ctx, True, 1.0),
                {"kind": "paragraph", "text": f"Word: {puzzle.solution['word']}"},
            ]
        )


__all__ = ["Level", "Wordoku", "word_ok"]
