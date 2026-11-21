"""Shift cipher (Caesar): every letter of a message is moved the same number of places along the
alphabet. No letter is given away; the reader finds the shift. The solver tries all 25 shifts and
accepts the puzzle only when exactly one of them turns every word into a dictionary word."""

from __future__ import annotations

import re
import string
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
from forge.wordlists.dictionary import is_word

SOLVER = "shift-try-all-v1"
AZ = string.ascii_uppercase
MIN_WORDS = 6


def move(text: str, k: int) -> str:
    return "".join(AZ[(AZ.index(c) + k) % 26] if c in AZ else c for c in text)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", text.upper())).strip()


def readings(cipher: str) -> list[tuple[int, str]]:
    """(shift back, plain text) for every shift whose words are all dictionary words."""
    out = []
    for k in range(1, 26):
        plain = move(cipher, -k)
        if all(is_word(w.lower()) or is_word(w) for w in plain.split()):
            out.append((k, plain))
    return out


class Shift:
    name = "shift"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        rng = make_rng(derive_seed(seed, "shift"))
        plain = clean(str(spec.options.get("text") or ""))
        if len(plain.split()) < MIN_WORDS:
            raise GenerationError(f"shift: the message needs at least {MIN_WORDS} words")
        ans = find_constraint(spec, AnswerIs)
        word = ans.word.upper() if ans else None
        if word and word not in plain.split():
            raise GenerationError(f"shift: the message does not contain {word}")
        k = rng.choice([s for s in range(3, 24) if s != 13])
        puzzle = build_puzzle(
            spec,
            seed,
            data={"cipher": move(plain, k)},
            solution={"shift": k, "plain": plain},
            token=word,
        )
        rep = self.verify(puzzle)
        if not rep.ok:
            raise GenerationError(f"shift failed verification: {rep.messages}")
        return puzzle.model_copy(update={"verify": rep, "difficulty": self.difficulty(puzzle)})

    def solve(self, puzzle: Puzzle) -> SolveResult:
        found = readings(puzzle.data["cipher"])
        if len(found) != 1:
            return SolveResult(solved=False, solutions_found=min(len(found), 2))
        k, plain = found[0]
        return SolveResult(solved=True, solution={"shift": k, "plain": plain}, solutions_found=1)

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        res = self.solve(puzzle)
        if not res.solved or res.solution is None:
            msgs.append(
                "no single shift gives a message of dictionary words "
                f"({res.solutions_found} readings)"
            )
        elif res.solution != puzzle.solution:
            msgs.append("solver reading differs from the stored message")
        if puzzle.token and puzzle.token not in puzzle.solution["plain"].split():
            msgs.append("the keyword is not a word of the message")
        if puzzle.data["cipher"] == puzzle.solution["plain"]:
            msgs.append("the message is not enciphered")
        return VerifyReport(ok=not msgs, unique=not msgs, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        words = puzzle.solution["plain"].split()
        short = sum(len(w) <= 3 for w in words)  # THE / AND / IT give the shift away quickly
        score = max(10.0, min(100.0, 55 - 4 * short + 0.5 * len(words)))
        return DifficultyScore(
            score=round(score, 1),
            label=level_from_score(score),
            features={"words": float(len(words)), "short_words": float(short)},
        )

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        blocks: list[dict[str, Any]] = [
            {
                "kind": "paragraph",
                "text": "Every letter of this message was moved the same number of places along "
                "the alphabet. Find the shift (try the shortest words first) and decode it.",
            },
            {"kind": "spacer", "height_in": 0.15},
            {"kind": "heading", "level": 2, "text": puzzle.data["cipher"]},
            {"kind": "spacer", "height_in": 0.25},
            {"kind": "paragraph", "text": "  ".join(AZ)},
            {"kind": "paragraph", "text": "Shift: ______     Message:"},
            {
                "kind": "answer_lines",
                "rows": [{"left": "", "right": ""}] * 3,
                "font_pt": 14.0,
                "pairs": 1,
                "gap_em": 2.0,
            },
        ]
        return RenderedBlock(blocks=blocks)

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        s = puzzle.solution
        return RenderedBlock(
            blocks=[{"kind": "paragraph", "text": f"Shift {s['shift']}: {s['plain']}"}]
        )
