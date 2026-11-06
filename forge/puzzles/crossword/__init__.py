"""Crossword (criss-cross). Modes: `fill_in` (default: fit the word list, provably unique)
and `clues` (numbered clues from `options.clues`, filled by the AI layer in P2.3)."""

from __future__ import annotations

from typing import Any

from forge.core.models import (
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
from forge.puzzles.base import GenerationError, clamp01
from forge.puzzles.crossword.generator import build
from forge.puzzles.crossword.grid import BLOCK, count_fill_solutions, numbering, read, slots

SOLVER = "crossword-fillin-v1"
MAX_ATTEMPTS = 40


def _shape(rows: list[str]) -> list[str]:
    return ["".join(BLOCK if ch == BLOCK else "." for ch in row) for row in rows]


def _key(cell: tuple[int, int]) -> str:
    return f"{cell[0]},{cell[1]}"


def _connected(rows: list[str]) -> bool:
    cells = {(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch != BLOCK}
    if not cells:
        return False
    seen, stack = set(), [next(iter(sorted(cells)))]
    while stack:
        r, c = stack.pop()
        if (r, c) in seen:
            continue
        seen.add((r, c))
        stack += [x for x in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)) if x in cells]
    return seen == cells


class Crossword:
    name = "crossword"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        mode = str(spec.options.get("mode", "fill_in"))
        clues: dict[str, str] = {k.upper(): v for k, v in spec.options.get("clues", {}).items()}
        for attempt in range(MAX_ATTEMPTS):
            rng = make_rng(derive_seed(seed, "crossword", attempt))
            built = build(spec, rng)
            if built is None:
                continue
            rows, words = built
            if mode == "clues" and any(w not in clues for w in words):
                continue
            givens: dict[tuple[int, int], str] = {}
            if mode == "fill_in":
                order = sorted(slots(rows), key=lambda s: (-s.length, s.r, s.c, s.dir))
                rng.shuffle(order)
                while count_fill_solutions(_shape(rows), words, givens) != 1 and order:
                    s = order.pop()
                    givens.update({cell: rows[cell[0]][cell[1]] for cell in s.cells()[:1]})
            data: dict[str, Any] = {
                "mode": mode,
                "shape": _shape(rows),
                "words": sorted(words, key=lambda w: (len(w), w)),
                "givens": {_key(c): ch for c, ch in sorted(givens.items())},
            }
            if mode == "clues":
                data["clues"] = {w: clues[w] for w in sorted(words)}
            puzzle = build_puzzle(spec, seed, data=data, solution={"rows": rows})
            report = self.verify(puzzle)
            if report.ok:
                return puzzle.model_copy(
                    update={"verify": report, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError(f"crossword: no valid grid for theme {spec.theme!r} ({mode})")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        givens = {
            (int(k.split(",")[0]), int(k.split(",")[1])): v
            for k, v in puzzle.data["givens"].items()
        }
        n = count_fill_solutions(puzzle.data["shape"], list(puzzle.data["words"]), givens)
        return SolveResult(solved=n >= 1, solutions_found=n)

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        rows: list[str] = puzzle.solution["rows"]
        msgs: list[str] = []
        if _shape(rows) != puzzle.data["shape"]:
            msgs.append("solution does not match the grid shape")
        entries = [read(rows, s) for s in slots(rows)]
        if sorted(entries) != sorted(puzzle.data["words"]):
            msgs.append(f"grid entries {sorted(entries)} != word list")
        if len(set(entries)) != len(entries):
            msgs.append("a word appears twice")
        if not _connected(rows):
            msgs.append("grid is not connected")
        for k, v in puzzle.data["givens"].items():
            r, c = map(int, k.split(","))
            if rows[r][c] != v:
                msgs.append(f"given {k}={v} is wrong")
        unique: bool | None = None
        if puzzle.data["mode"] == "fill_in":
            unique = self.solve(puzzle).solutions_found == 1
            if not unique:
                msgs.append("fill-in has more than one solution")
        else:
            missing = [w for w in entries if not puzzle.data.get("clues", {}).get(w)]
            if missing:
                msgs.append(f"missing clues for {missing}")
        return VerifyReport(ok=not msgs, unique=unique, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        rows = puzzle.solution["rows"]
        words = puzzle.data["words"]
        n_cells = sum(ch != BLOCK for row in rows for ch in row)
        f = {
            "word_count": clamp01((len(words) - 6) / (20 - 6)),
            "area": clamp01((len(rows) * len(rows[0]) - 49) / (289 - 49)),
            "givens": 1 - clamp01(len(puzzle.data["givens"]) / max(n_cells, 1) * 8),
        }
        score = round(min(100.0, 8 + 80 * f["word_count"] + 4 * f["area"] + 3 * f["givens"]), 1)
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _grid(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool, share: float) -> dict[str, Any]:
        rows: list[str] = puzzle.solution["rows"]
        nums = numbering(rows) if puzzle.data["mode"] == "clues" else {}
        givens = puzzle.data["givens"]
        h, w = len(rows), len(rows[0])
        cell = round(min(ctx.width_in / w, ctx.height_in * share / h, 0.55), 3)
        grid: list[list[dict[str, Any] | None]] = []
        for r, row in enumerate(rows):
            line: list[dict[str, Any] | None] = []
            for c, ch in enumerate(row):
                if ch == BLOCK:
                    line.append(None)
                    continue
                shown = ch if solution else givens.get(_key((r, c)), "")
                line.append({"n": nums.get((r, c), 0), "ch": shown})
            grid.append(line)
        return {
            "kind": "crossword_grid",
            "cells": grid,
            "cell_in": cell,
            "font_pt": round(cell * 72 * 0.55, 1),
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        blocks: list[dict[str, Any]] = [self._grid(puzzle, ctx, False, 0.6)]
        size = 16.0 if ctx.large_print else 11.0
        if puzzle.data["mode"] == "fill_in":
            blocks.insert(
                0,
                {
                    "kind": "paragraph",
                    "text": "Fit every word into the grid. "
                    "Some letters are given to get you started.",
                },
            )
            by_len: dict[int, list[str]] = {}
            for wd in puzzle.data["words"]:
                by_len.setdefault(len(wd), []).append(wd)
            for n, ws in sorted(by_len.items()):
                blocks.append({"kind": "paragraph", "text": f"{n} letters:  " + "   ".join(ws)})
        else:
            rows = puzzle.solution["rows"]
            nums = numbering(rows)
            clues = puzzle.data["clues"]
            for d, title in (("A", "Across"), ("D", "Down")):
                items = [
                    f"{nums[(s.r, s.c)]}. {clues[read(rows, s)]}" for s in slots(rows) if s.dir == d
                ]
                blocks.append({"kind": "heading", "level": 2, "text": title})
                blocks.append({"kind": "list", "items": items})
        for b in blocks:
            if b["kind"] == "paragraph":
                b["font_pt"] = size
        return RenderedBlock(blocks=blocks)

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(blocks=[self._grid(puzzle, ctx, True, 1.0)])
