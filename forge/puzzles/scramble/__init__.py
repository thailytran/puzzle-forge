"""Word scramble: unscramble theme words; every scramble has exactly one answer."""

from __future__ import annotations

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


@dataclass(frozen=True)
class ScParams:
    min_len: int
    max_len: int
    count: int
    max_kept_pairs: int  # adjacent letter pairs allowed to stay in original order


_BY_LEVEL: dict[Level, ScParams] = {
    "very_easy": ScParams(3, 4, 8, 1),
    "easy": ScParams(4, 5, 10, 1),
    "medium": ScParams(5, 7, 12, 1),
    "hard": ScParams(7, 9, 12, 0),
    "expert": ScParams(8, 14, 12, 0),
}


def resolve_params(spec: PuzzleSpec) -> ScParams:
    p = _BY_LEVEL[spec.level]
    if spec.audience == "kids_6_8":
        p = replace(p, min_len=min(p.min_len, 3), max_len=min(p.max_len, 6), count=min(p.count, 10))
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

        def off_band(w: str) -> int:  # prefer the level's lengths, then the nearest ones
            return max(p.min_len - len(w), len(w) - p.max_len, 0)

        eligible.sort(key=off_band)
        items: list[dict[str, str]] = []
        for w in eligible:
            if len(items) >= p.count:
                break
            s = scramble_word(w, p, rng)
            if s:
                items.append({"scrambled": s, "answer": w})
        if len(items) < min(p.count, 5):
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
            "avg_len": clamp01((avg_len - 3) / (10 - 3)),
            "count": clamp01((len(answers) - 6) / (14 - 6)),
            "scrambledness": 1 - clamp01(kept / max(len(answers), 1)),
        }
        score = round(
            5 + 90 * (0.75 * f["avg_len"] + 0.1 * f["count"] + 0.15 * f["scrambledness"]), 1
        )
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _lines(self, puzzle: Puzzle, solution: bool) -> list[dict[str, Any]]:
        rows = [
            {"left": f"{i}.  {' '.join(s)}", "right": a if solution else ""}
            for i, (s, a) in enumerate(
                zip(puzzle.data["items"], puzzle.solution["answers"], strict=True), 1
            )
        ]
        return rows

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        size = 16.0 if ctx.large_print else 13.0
        blocks: list[dict[str, Any]] = [
            {"kind": "paragraph", "text": "Unscramble each word. Every word fits the theme."},
            {"kind": "answer_lines", "rows": self._lines(puzzle, False), "font_pt": size},
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
        return RenderedBlock(blocks=[{"kind": "answer_lines", "rows": rows, "font_pt": 11.0}])
