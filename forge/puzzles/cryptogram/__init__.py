"""Cryptogram: a public-domain quote (or given text) under a letter-substitution cipher.

Uniqueness: a dictionary-pattern solver (ENABLE) counts every decoding consistent with the
hint letters. Hints are added until exactly one decoding exists.
"""

from __future__ import annotations

import random
import string
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
from forge.wordlists import normalize_word
from forge.wordlists.dictionary import by_pattern, is_common, pattern, quotes

SOLVER = "cryptogram-pattern-v1"
NODE_LIMIT = 300_000
HINT_CANDIDATES = 8  # letters tried per greedy hint step (most frequent first)
ALPHA = string.ascii_uppercase


@dataclass(frozen=True)
class CgParams:
    min_words: int
    max_words: int
    hints: int


_BY_LEVEL: dict[Level, CgParams] = {
    "very_easy": CgParams(3, 6, 5),
    "easy": CgParams(4, 8, 3),
    "medium": CgParams(5, 10, 1),
    "hard": CgParams(6, 14, 0),
    "expert": CgParams(9, 30, 0),
}


def resolve_params(spec: PuzzleSpec) -> CgParams:
    p = _BY_LEVEL[spec.level]
    if spec.audience == "kids_6_8":
        p = replace(p, max_words=min(p.max_words, 7), hints=max(p.hints, 4))
    if "hints" in spec.options:
        p = replace(p, hints=int(spec.options["hints"]))
    return p


def plain_words(text: str) -> list[str]:
    return [normalize_word(w) for w in text.split() if normalize_word(w)]


def derangement(rng: random.Random) -> dict[str, str]:
    while True:
        perm = list(ALPHA)
        rng.shuffle(perm)
        if all(a != b for a, b in zip(ALPHA, perm, strict=True)):
            return dict(zip(ALPHA, perm, strict=True))


def encipher(text: str, key: dict[str, str]) -> str:
    return "".join(key.get(ch, ch) for ch in text.upper())


# --------------------------------------------------------------------------- solver


def _options(cw: str, fixed: dict[str, str]) -> list[str]:
    if all(ch in fixed for ch in cw):
        return ["".join(fixed[ch] for ch in cw)]
    used = {v: k for k, v in fixed.items()}
    out = []
    for pw in by_pattern().get(pattern(cw), ()):
        for c, p in zip(cw, pw, strict=True):
            if c == p or (c in fixed and fixed[c] != p) or (c not in fixed and p in used):
                break
        else:
            out.append(pw)
    return out


def ambiguity(cipher_words: list[str], fixed: dict[str, str]) -> dict[str, int]:
    """Number of dictionary options per cipher word under the current hints."""
    return {cw: len(_options(cw, fixed)) for cw in set(cipher_words)}


def count_decodings(
    cipher_words: list[str], fixed: dict[str, str], limit: int = 2
) -> tuple[int, bool]:
    """(#decodings found ≤ limit, completed). `fixed` maps cipher → plain letters.

    Backtracking over whole words with dynamic ordering: always expand the word with the
    fewest options consistent with the letters decided so far.
    """
    words = sorted(set(cipher_words))
    found = 0
    nodes = 0

    def rec(mapping: dict[str, str], remaining: list[str]) -> bool:
        nonlocal found, nodes
        if not remaining:
            found += 1
            return found >= limit
        best: list[str] | None = None
        best_word = ""
        for cw in remaining:
            opts = _options(cw, mapping)
            if not opts:
                return False
            if best is None or len(opts) < len(best):
                best, best_word = opts, cw
                if len(opts) == 1:
                    break
        assert best is not None
        rest = [w for w in remaining if w != best_word]
        for pw in best:
            nodes += 1
            if nodes > NODE_LIMIT:
                return True
            nxt = dict(mapping)
            nxt.update(zip(best_word, pw, strict=True))
            if rec(nxt, rest):
                return True
        return False

    rec(dict(fixed), words)
    return found, nodes <= NODE_LIMIT


def best_hint(
    cipher_words: list[str],
    words: list[str],
    letters: list[str],
    hinted: set[str],
    key: dict[str, str],
) -> str:
    """Greedy: the plain letter whose reveal leaves the fewest decodings (ties → frequent)."""
    freq = {ch: sum(w.count(ch) for w in words) for ch in letters}
    best, best_n = "", 10**9
    open_letters = sorted((c for c in letters if c not in hinted), key=lambda c: (-freq[c], c))
    for ch in open_letters[:HINT_CANDIDATES]:
        fixed = {key[x]: x for x in hinted | {ch}}
        n, done = count_decodings(cipher_words, fixed, limit=10)
        n = n if done else 10**6
        if n < best_n:
            best, best_n = ch, n
            if n == 1:
                break
    return best


class Cryptogram:
    name = "cryptogram"

    def _source(self, spec: PuzzleSpec, p: CgParams, rng: random.Random) -> tuple[str, str]:
        ans = find_constraint(spec, AnswerIs)
        if "text" in spec.options:
            return str(spec.options["text"]).upper(), str(spec.options.get("source", ""))
        if ans is not None:
            return f"THE ANSWER IS {normalize_word(ans.word)}.", ""
        pool = [(t, s) for t, s in quotes() if p.min_words <= len(plain_words(t)) <= p.max_words]
        if not pool:
            raise GenerationError("cryptogram: no quote fits this level")
        text, source = pool[rng.randrange(len(pool))]
        return text.upper(), source

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        p = resolve_params(spec)
        ans = find_constraint(spec, AnswerIs)
        for attempt in range(10):
            rng = make_rng(derive_seed(seed, "cryptogram", attempt))
            plain, source = self._source(spec, p, rng)
            key = derangement(rng)
            words = plain_words(plain)
            letters = sorted({ch for w in words for ch in w})
            # letters of uncommon words (names...) are always given
            hinted = {ch for w in words if not is_common(w) for ch in w}
            extra = [ch for ch in letters if ch not in hinted]
            rng.shuffle(extra)
            hinted.update(extra[: p.hints])
            cipher_words = [encipher(w, key) for w in words]
            while True:
                fixed = {key[ch]: ch for ch in hinted}
                n, done = count_decodings(cipher_words, fixed)
                if (n == 1 and done) or len(hinted) == len(letters):
                    break
                hinted.add(best_hint(cipher_words, words, letters, hinted, key))
            if not (n == 1 and done):
                continue
            puzzle = build_puzzle(
                spec,
                seed,
                data={
                    "cipher": encipher(plain, key),
                    "hints": {key[ch]: ch for ch in sorted(hinted)},
                    "source": source,
                },
                solution={"plain": plain, "key": {k: v for k, v in key.items() if k in letters}},
                token=normalize_word(ans.word) if ans else None,
            )
            report = self.verify(puzzle)
            if report.ok:
                return puzzle.model_copy(
                    update={"verify": report, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError("cryptogram: could not build a uniquely solvable puzzle")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        cipher: str = puzzle.data["cipher"]
        words = [w for w in (normalize_word(x) for x in cipher.split()) if w]
        n, done = count_decodings(words, dict(puzzle.data["hints"]))
        return SolveResult(
            solved=n >= 1, solutions_found=n if done else 2, stats={"complete": float(done)}
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        key: dict[str, str] = puzzle.solution["key"]
        plain: str = puzzle.solution["plain"]
        if any(k == v for k, v in key.items()):
            msgs.append("a letter maps to itself")
        if len(set(key.values())) != len(key):
            msgs.append("key is not one-to-one")
        if encipher(plain, key) != puzzle.data["cipher"]:
            msgs.append("cipher does not match plaintext under the key")
        inverse = {v: k for k, v in key.items()}
        for c, p in puzzle.data["hints"].items():
            if inverse.get(c) != p:
                msgs.append(f"hint {c}={p} is wrong")
        res = self.solve(puzzle)
        if res.solutions_found != 1:
            msgs.append(f"{res.solutions_found} decodings fit the dictionary (need exactly 1)")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and normalize_word(ans.word) not in plain_words(plain):
            msgs.append("answer word not in the plaintext")
        return VerifyReport(
            ok=not msgs, unique=res.solutions_found == 1, solver=SOLVER, messages=msgs
        )

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        plain = puzzle.solution["plain"]
        n_letters = len(puzzle.solution["key"])
        hints = len(puzzle.data["hints"])
        total = sum(len(w) for w in plain_words(plain))
        f = {
            "hint_ratio": 1 - clamp01(hints / max(n_letters, 1) / 0.6),
            "length": clamp01((total - 15) / (75 - 15)),
            "distinct_letters": clamp01((n_letters - 8) / (20 - 8)),
        }
        score = round(
            5 + 90 * (0.45 * f["hint_ratio"] + 0.35 * f["length"] + 0.2 * f["distinct_letters"]),
            1,
        )
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _block(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool) -> dict[str, Any]:
        key = puzzle.solution["key"]
        inverse = {v: k for k, v in key.items()}
        hints = puzzle.data["hints"]
        words = []
        for cw in puzzle.data["cipher"].split():
            cells = []
            for ch in cw:
                if ch in ALPHA:
                    shown = inverse[ch] if solution else hints.get(ch, "")
                    cells.append({"c": ch, "p": shown})
                else:
                    cells.append({"c": "", "p": ch})
            words.append(cells)
        return {
            "kind": "cryptogram",
            "words": words,
            "font_pt": 20.0 if ctx.large_print else 16.0,
            "source": puzzle.data.get("source", ""),
        }

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[
                {
                    "kind": "paragraph",
                    "text": "Each letter stands for another letter. Crack the code to reveal "
                    "the message. Some letters are given to get you started.",
                },
                self._block(puzzle, ctx, False),
            ]
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(blocks=[self._block(puzzle, ctx, True)])
