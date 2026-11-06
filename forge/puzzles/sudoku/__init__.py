"""Sudoku puzzle type (4x4, 6x6, 9x9)."""

from __future__ import annotations

from forge.core.models import (
    DifficultyScore,
    Level,
    Puzzle,
    PuzzleSpec,
    ShadedCells,
    SolveResult,
    VerifyReport,
    build_puzzle,
)
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.core.seeds import derive_seed, make_rng
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.sudoku import difficulty as _difficulty
from forge.puzzles.sudoku import render as _render
from forge.puzzles.sudoku import solver as _solver
from forge.puzzles.sudoku.generator import build
from forge.puzzles.sudoku.grading import band_distance
from forge.puzzles.sudoku.grid import Grid

MAX_ATTEMPTS = 80


class Sudoku:
    name = "sudoku"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        best: tuple[int, Grid, Grid] | None = None
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "sudoku", attempt))
            built = build(spec, rng)
            if built is None:
                continue
            givens, solution, level = built
            dist = band_distance(level, spec.level)
            if best is None or dist < best[0]:
                best = (dist, givens, solution)
            if dist == 0:
                break
        if best is None:
            raise GenerationError(f"sudoku: no valid puzzle for {spec}")
        _, givens, solution = best
        return self._finish(spec, seed, givens, solution)

    def _finish(self, spec: PuzzleSpec, seed: int, givens: Grid, solution: Grid) -> Puzzle:
        sc = find_constraint(spec, ShadedCells)
        token = "".join(str(solution[r][c]) for r, c in sc.cells) if sc else None
        puzzle = build_puzzle(
            spec,
            seed,
            data={"size": len(givens), "givens": givens},
            solution={"grid": solution},
            token=token,
        )
        report = self.verify(puzzle)
        if not report.ok:
            raise GenerationError(f"sudoku failed verification: {report.messages}")
        return puzzle.model_copy(update={"verify": report, "difficulty": self.difficulty(puzzle)})

    def solve(self, puzzle: Puzzle) -> SolveResult:
        return _solver.solve(puzzle)

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        return _solver.verify(puzzle)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        return _difficulty.difficulty(puzzle)

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return _render.render(puzzle, ctx)

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return _render.render_solution(puzzle, ctx)


__all__ = ["Level", "Sudoku"]
