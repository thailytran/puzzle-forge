"""Word scramble: unscramble theme words; every scramble has exactly one answer."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, replace
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
from forge.puzzles.base import GenerationError, clamp01, find_constraint
from forge.wordlists import blocklist, normalize_word, theme_words
from forge.wordlists.dictionary import anagrams, is_word

SOLVER = "scramble-anagram-v1"
MIN_ITEMS = 16  # a page needs at least this many unique-answer words (target 20)
# target average word length per level (the page average decides the measured level)
TARGET_AVG_LEN: dict[str, float] = {
    "very_easy": 5.0,
    "easy": 5.4,
    "medium": 6.1,
    "hard": 7.3,
    "expert": 8.6,
}
# Beginner: first + last letter shown on the answer line; Easy: first letter (classic aid)
HINT_MODE: dict[str, str] = {"very_easy": "first_last", "easy": "first"}
HINT_FACTOR: dict[str | None, float] = {"first_last": 0.4, "first": 0.8, None: 1.0}


def _hint(answer: str, mode: str | None) -> str:
    """Answer-line pattern, e.g. 'B _ _ _ T' (empty string = plain line)."""
    if not mode:
        return ""
    cells = ["_"] * len(answer)
    cells[0] = answer[0]
    if mode == "first_last":
        cells[-1] = answer[-1]
    return " ".join(cells)


LEN_TO_SCORE = ((4.0, 5.0), (4.9, 20.0), (5.6, 40.0), (6.6, 60.0), (8.0, 80.0), (9.5, 95.0))


def _interp(x: float, pts: tuple[tuple[float, float], ...]) -> float:
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in itertools.pairwise(pts):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


@dataclass(frozen=True)
class ScParams:
    min_len: int
    max_len: int
    count: int
    max_kept_pairs: int  # adjacent letter pairs allowed to stay in original order


_BY_LEVEL: dict[Level, ScParams] = {
    # owner decision 2026-11-07: 20 words per page at every level
    "very_easy": ScParams(3, 4, 20, 1),
    "easy": ScParams(4, 5, 20, 1),
    "medium": ScParams(5, 7, 20, 1),
    "hard": ScParams(7, 9, 20, 0),
    "expert": ScParams(8, 14, 20, 0),
}


def resolve_params(spec: PuzzleSpec) -> ScParams:
    p = _BY_LEVEL[spec.level]
    if spec.audience == "kids_6_8":
        p = replace(p, min_len=min(p.min_len, 3), max_len=min(p.max_len, 6), count=p.count)
    if "count" in spec.options:
        p = replace(p, count=int(spec.options["count"]))
    return p


def _pool(spec: PuzzleSpec) -> list[str]:
    raw = spec.words if spec.words else list(theme_words(spec.theme or "animals"))
    return list(dict.fromkeys(normalize_word(w) for w in raw if normalize_word(w)))


def candidates(scrambled: str, context: list[str]) -> set[str]:
    """Every word (dictionary + the puzzle's own word bank) these letters spell."""
    sig = sorted(scrambled)
    return set(anagrams(scrambled)) | {w for w in context if sorted(w) == sig}


def unique_answer(word: str, context: list[str]) -> bool:
    return candidates(word, context) == {word}


def kept_pairs(word: str, scrambled: str) -> int:
    pairs = {word[i : i + 2] for i in range(len(word) - 1)}
    return sum(scrambled[i : i + 2] in pairs for i in range(len(scrambled) - 1))


def scramble_word(word: str, p: ScParams, rng: random.Random) -> str | None:
    letters = list(word)
    for _ in range(300):
        rng.shuffle(letters)
        s = "".join(letters)
        if s == word or is_word(s) or kept_pairs(word, s) > p.max_kept_pairs:
            continue
        if any(b in s for b in blocklist() if len(b) >= 3):
            continue
        return s
    return None


class Scramble:
    name = "scramble"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        p = resolve_params(spec)
        pool = _pool(spec)
        ans = find_constraint(spec, AnswerIs)
        bonus_word = normalize_word(ans.word) if ans else None
        if bonus_word:
            if not (is_word(bonus_word) or bonus_word in pool):
                raise GenerationError(f"scramble: {bonus_word!r} is not a dictionary/theme word")
            if not unique_answer(bonus_word, pool):
                raise GenerationError(f"scramble: {bonus_word!r} has other anagrams; pick another")
        rng = make_rng(derive_seed(seed, "scramble"))
        eligible = [w for w in pool if len(w) >= 3 and w != bonus_word and unique_answer(w, pool)]
        rng.shuffle(eligible)

        target = TARGET_AVG_LEN[spec.level]
        eligible.sort(key=lambda w: abs(len(w) - target))  # shuffled first: random tie-break
        items: list[dict[str, str]] = []
        for w in eligible:
            if len(items) >= p.count:
                break
            s = scramble_word(w, p, rng)
            if s:
                items.append({"scrambled": s, "answer": w})
        if len(items) < min(p.count, MIN_ITEMS):
            raise GenerationError(f"scramble: only {len(items)} usable words for {spec.theme!r}")
        bonus: dict[str, str] | None = None
        if bonus_word:
            s = scramble_word(bonus_word, replace(p, max_kept_pairs=len(bonus_word)), rng)
            if s is None:
                raise GenerationError(f"scramble: cannot scramble {bonus_word!r}")
            bonus = {"scrambled": s, "answer": bonus_word}
        puzzle = build_puzzle(
            spec,
            seed,
            data={
                "items": [i["scrambled"] for i in items],
                "hint_mode": HINT_MODE.get(spec.level),
                "bonus": bonus["scrambled"] if bonus else None,
                "word_bank": sorted(pool),
            },
            solution={
                "answers": [i["answer"] for i in items],
                "bonus": bonus["answer"] if bonus else None,
            },
            token=bonus_word,
        )
        report = self.verify(puzzle)
        if not report.ok:
            raise GenerationError(f"scramble failed verification: {report.messages}")
        return puzzle.model_copy(update={"verify": report, "difficulty": self.difficulty(puzzle)})

    def solve(self, puzzle: Puzzle) -> SolveResult:
        bank: list[str] = puzzle.data["word_bank"]
        found: list[list[str]] = [sorted(candidates(s, bank)) for s in puzzle.data["items"]]
        bonus = puzzle.data.get("bonus")
        bonus_c = sorted(candidates(bonus, bank)) if bonus else []
        unique = all(len(f) == 1 for f in found) and (not bonus or len(bonus_c) == 1)
        return SolveResult(
            solved=all(found) and (not bonus or bool(bonus_c)),
            solution={"candidates": found, "bonus": bonus_c},
            solutions_found=1 if unique else 2,
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        res = self.solve(puzzle)
        sol = res.solution or {}
        for s, cands, ans in zip(
            puzzle.data["items"], sol.get("candidates", []), puzzle.solution["answers"], strict=True
        ):
            if cands != [ans]:
                msgs.append(f"{s}: solutions {cands}, expected [{ans}]")
            if s == ans:
                msgs.append(f"{s} is not scrambled")
        bonus = puzzle.solution.get("bonus")
        if bonus is not None:
            bc = sol.get("bonus", [])
            if bc != [bonus]:
                msgs.append(f"bonus: solutions {bc}, expected [{bonus}]")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and normalize_word(ans.word) != bonus:
            msgs.append("bonus answer differs from answer_is constraint")
        return VerifyReport(ok=not msgs, unique=not msgs, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        answers: list[str] = puzzle.solution["answers"]
        avg_len = sum(map(len, answers)) / len(answers)
        kept = sum(kept_pairs(a, s) for a, s in zip(answers, puzzle.data["items"], strict=True))
        f = {
            "avg_len": round(avg_len, 3),
            "count": float(len(answers)),
            "scrambledness": 1 - clamp01(kept / max(len(answers), 1)),
        }
        # average word length drives difficulty; breakpoints fitted on 20-word pages (2026-11-07)
        f["hint_factor"] = HINT_FACTOR[puzzle.data.get("hint_mode")]
        score = _interp(avg_len, LEN_TO_SCORE) * f["hint_factor"] + 3 * (f["scrambledness"] - 0.5)
        score = round(min(100.0, max(0.0, score)), 1)
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _lines(self, puzzle: Puzzle, solution: bool) -> list[dict[str, Any]]:
        mode = puzzle.data.get("hint_mode")
        rows = [
            {"left": f"{i}.  {' '.join(s)}", "right": a if solution else _hint(a, mode)}
            for i, (s, a) in enumerate(
                zip(puzzle.data["items"], puzzle.solution["answers"], strict=True), 1
            )
        ]
        return rows

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        size = 16.0 if ctx.large_print else 13.0
        blocks: list[dict[str, Any]] = [
            {"kind": "paragraph", "text": "Unscramble each word. Every word fits the theme."},
            {
                "kind": "answer_lines",
                "rows": self._lines(puzzle, False),
                "font_pt": size,
                "pairs": 2 if len(puzzle.data["items"]) > 12 else 1,
                "gap_em": 1.3,
            },
        ]
        if puzzle.data.get("bonus"):
            blocks += [
                {"kind": "spacer", "height_in": 0.2},
                {"kind": "heading", "level": 2, "text": "Secret word"},
                {
                    "kind": "answer_lines",
                    "rows": [{"left": " ".join(puzzle.data["bonus"]), "right": ""}],
                    "font_pt": size,
                },
            ]
        return RenderedBlock(blocks=blocks)

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        rows = self._lines(puzzle, True)
        if puzzle.data.get("bonus"):
            rows.append(
                {
                    "left": f"Secret:  {' '.join(puzzle.data['bonus'])}",
                    "right": puzzle.solution["bonus"],
                }
            )
        size = 11.0 if ctx.width_in > 5 else 8.0
        block = {"kind": "answer_lines", "rows": rows, "font_pt": size, "pairs": 2, "gap_em": 0.45}
        return RenderedBlock(blocks=[block])
