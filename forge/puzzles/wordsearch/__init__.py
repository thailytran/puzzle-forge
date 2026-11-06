"""Word search puzzle type."""

from __future__ import annotations

from forge.core.models import DifficultyScore, HiddenMessage, Puzzle, PuzzleSpec, SolveResult
from forge.core.models import VerifyReport as VerifyReport
from forge.core.protocol import RenderCtx, RenderedBlock
from forge.core.seeds import derive_seed, make_rng
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.wordsearch import difficulty as _difficulty
from forge.puzzles.wordsearch import render as _render
from forge.puzzles.wordsearch import solver as _solver
from forge.puzzles.wordsearch.generator import build_draft, require_words
from forge.puzzles.wordsearch.params import resolve_params
from forge.wordlists import normalize_word

MAX_ATTEMPTS = 60


class WordSearch:
    name = "wordsearch"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        from forge.core.models import build_puzzle

        require_words(spec)
        p = resolve_params(spec.level, spec.audience, spec.size, spec.options)
        hidden = find_constraint(spec, HiddenMessage)
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "wordsearch", attempt))
            draft = build_draft(spec, p, rng)
            if draft is None:
                continue
            placements = sorted(draft.placements)
            puzzle = build_puzzle(
                spec,
                seed,
                data={
                    "rows": draft.as_rows(),
                    "words": sorted(w for w, *_ in placements),
                    "directions": list(p.dirs),
                    "shape": p.shape,
                    "decoys": 0 if hidden else p.decoys,
                    "word_letter_fill": p.word_letter_fill,
                },
                solution={
                    "placements": [
                        {"word": w, "row": r, "col": c, "dir": d} for w, r, c, d in placements
                    ],
                    "hidden_message": normalize_word(hidden.text) if hidden else None,
                },
                token=normalize_word(hidden.text) if hidden else None,
            )
            report = self.verify(puzzle)
            if report.ok:
                return puzzle.model_copy(
                    update={"verify": report, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError(
            f"wordsearch: no valid puzzle after {MAX_ATTEMPTS} attempts "
            f"(level={spec.level}, words={len(spec.words or [])}, constraints={spec.constraints})"
        )

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
