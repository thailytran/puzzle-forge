"""Maze puzzle type."""

from __future__ import annotations

from forge.core.models import (
    DifficultyScore,
    PathLetters,
    Puzzle,
    PuzzleSpec,
    SolveResult,
    VerifyReport,
    build_puzzle,
)
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.core.seeds import derive_seed, make_rng
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.maze import difficulty as _difficulty
from forge.puzzles.maze import render as _render
from forge.puzzles.maze import solver as _solver
from forge.puzzles.maze.generator import build

MAX_ATTEMPTS = 20


class Maze:
    name = "maze"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        pl = find_constraint(spec, PathLetters)
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "maze", attempt))
            try:
                cells, path, letters = build(spec, rng)
            except GenerationError as exc:  # e.g. route too short for the letters
                last = exc
                continue
            token = "".join(ch for ch in pl.seq.upper() if ch.isalnum()) if pl else None
            puzzle = build_puzzle(
                spec,
                seed,
                data={
                    "cells": cells,
                    "rows": len(cells),
                    "cols": len(cells[0]),
                    "start": [0, 0],
                    "goal": [len(cells) - 1, len(cells[0]) - 1],
                    "letters": letters,
                },
                solution={"path": [list(x) for x in path]},
                token=token,
            )
            report = self.verify(puzzle)
            if report.ok:
                return puzzle.model_copy(
                    update={"verify": report, "difficulty": self.difficulty(puzzle)}
                )
            last = GenerationError(str(report.messages))
        raise GenerationError(f"maze: no valid puzzle ({last})")

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
