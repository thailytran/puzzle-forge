"""Cryptogram: a public-domain quote (or given text) under a letter-substitution cipher.

Uniqueness: a dictionary-pattern solver (ENABLE) counts every decoding consistent with the
hint letters. Hints are added until exactly one decoding exists.
"""

from __future__ import annotations

import itertools
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
from forge.puzzles.base import GenerationError, find_constraint
from forge.wordlists import normalize_word
from forge.wordlists.dictionary import by_pattern, is_common, pattern, quotes

SOLVER = "cryptogram-pattern-v1"
NODE_LIMIT = 300_000
HINT_CANDIDATES = 8  # letters tried per greedy hint step (most frequent first)
ALPHA = string.ascii_uppercase
MIN_QUOTES = 5
# page-average letters per quote at the centre of each level's band (LETTERS_TO_SCORE), so the
# measured level matches on the first try (the uniqueness proof is the slow part)
TARGET_LETTERS: dict[str, float] = {
    "very_easy": 18.0,
    "easy": 24.0,
    "medium": 28.0,
    "hard": 33.0,
    "expert": 41.0,
}
LETTERS_TO_SCORE = (
    (16.0, 5.0),
    (22.0, 20.0),
    (26.0, 40.0),
    (30.0, 60.0),
    (36.0, 80.0),
    (46.0, 95.0),
)


def _interp(x: float, pts: tuple[tuple[float, float], ...]) -> float:
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in itertools.pairwise(pts):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


@dataclass(frozen=True)
class CgParams:
    count: int  # quotes per page (owner: 5-10)
    target_words: float  # preferred quote length
    hints: int  # minimum given letters per quote (more are added until unique)


_BY_LEVEL: dict[Level, CgParams] = {
    "very_easy": CgParams(10, 4.5, 5),
    "easy": CgParams(10, 6.0, 3),
    "medium": CgParams(9, 7.5, 1),
    "hard": CgParams(8, 9.5, 0),
    "expert": CgParams(7, 12.0, 0),
}
# page budget in "lines" of cipher cells (≈ 36 letters/line at 12 pt, 27 at 16 pt large print)
PAGE_LINES = {"normal": 18, "large": 13}
LINE_CHARS = {"normal": 36, "large": 27}
FONT_PT = {"normal": 12.0, "large": 16.0}


def resolve_params(spec: PuzzleSpec) -> CgParams:
    p = _BY_LEVEL[spec.level]
    if spec.audience == "kids_6_8":
        p = replace(p, hints=max(p.hints, 4), target_words=min(p.target_words, 6.0))
    if spec.audience == "senior_large_print":  # 16 pt cells: shorter quotes so >= 5 fit a page
        p = replace(p, target_words=min(p.target_words, 6.0), count=min(p.count, 7))
    if "hints" in spec.options:
        p = replace(p, hints=int(spec.options["hints"]))
    if "count" in spec.options:
        p = replace(p, count=int(spec.options["count"]))
    return p


def quote_id(text: str) -> str:
    """Short stable id of a quote (book-level dedupe via options.exclude)."""
    import hashlib

    return hashlib.sha256(normalize_word(text).encode()).hexdigest()[:10]


def show_source(source: str) -> bool:
    """Proverbs are anonymous: print a source line only for a named author."""
    return bool(source) and source not in ("Proverb", "Original")


def lines_needed(text: str, large: bool) -> int:
    width = LINE_CHARS["large" if large else "normal"]
    lines, cur = 1, 0
    for w in text.split():
        n = len(w) + 1
        if cur + n > width:
            lines, cur = lines + 1, n
        else:
            cur += n
    return lines


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


def _one_quote(plain: str, source: str, p: CgParams, rng: random.Random) -> dict[str, Any] | None:
    """Encipher one quote and add hints until its decoding is provably unique."""
    key = derangement(rng)
    words = plain_words(plain)
    letters = sorted({ch for w in words for ch in w})
    hinted = {ch for w in words if not is_common(w) for ch in w}  # names etc. are always given
    extra = [ch for ch in letters if ch not in hinted]
    rng.shuffle(extra)
    hinted.update(extra[: p.hints])
    cipher_words = [encipher(w, key) for w in words]
    while True:
        n, done = count_decodings(cipher_words, {key[ch]: ch for ch in hinted})
        if (n == 1 and done) or len(hinted) == len(letters):
            break
        hinted.add(best_hint(cipher_words, words, letters, hinted, key))
    if not (n == 1 and done):
        return None
    return {
        "cipher": encipher(plain, key),
        "hints": {key[ch]: ch for ch in sorted(hinted)},
        "source": source,
        "plain": plain,
        "key": {k: v for k, v in key.items() if k in letters},
    }


class Cryptogram:
    name = "cryptogram"

    def _texts(self, spec: PuzzleSpec, p: CgParams, rng: random.Random) -> list[tuple[str, str]]:
        ans = find_constraint(spec, AnswerIs)
        if "text" in spec.options:
            return [(str(spec.options["text"]).upper(), str(spec.options.get("source", "")))]
        if ans is not None:
            return [(f"THE ANSWER IS {normalize_word(ans.word)}.", "")]
        exclude = set(spec.options.get("exclude", []))
        if spec.options.get("quotes"):  # content plan: this page's quotes (PD or original)
            pool = [
                (str(q["text"]), str(q.get("source", "Original"))) for q in spec.options["quotes"]
            ]
        else:
            pool = list(quotes())
        pool = [(t, src) for t, src in pool if quote_id(t) not in exclude]
        rng.shuffle(pool)
        target = TARGET_LETTERS[spec.level]

        def letters(t: str) -> int:
            return sum(len(w) for w in plain_words(t))

        pool.sort(key=lambda q: abs(letters(q[0]) - target))
        large = spec.audience == "senior_large_print"
        budget = 2 * PAGE_LINES["large" if large else "normal"]  # in half-lines
        chosen: list[tuple[str, str]] = []
        used = 0
        for t, src in pool:
            if len(chosen) >= p.count:
                break
            need = 2 * lines_needed(t, large) + 1 + (1 if show_source(src) else 0)
            if used + need > budget:
                continue
            chosen.append((t.upper(), src))
            used += need
        if len(chosen) < min(p.count, MIN_QUOTES):
            raise GenerationError(
                f"cryptogram: only {len(chosen)} unused quotes fit (book exhausted the quote bank)"
            )
        return chosen

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        p = resolve_params(spec)
        ans = find_constraint(spec, AnswerIs)
        for attempt in range(5):
            rng = make_rng(derive_seed(seed, "cryptogram", attempt))
            texts = self._texts(spec, p, rng)
            items = [_one_quote(t, src, p, rng) for t, src in texts]
            if any(x is None for x in items):
                continue
            qs = [x for x in items if x is not None]
            puzzle = build_puzzle(
                spec,
                seed,
                data={
                    "quotes": [
                        {"cipher": q["cipher"], "hints": q["hints"], "source": q["source"]}
                        for q in qs
                    ],
                    "large": spec.audience == "senior_large_print",
                },
                solution={"quotes": [{"plain": q["plain"], "key": q["key"]} for q in qs]},
                token=normalize_word(ans.word) if ans else None,
            )
            report = self.verify(puzzle)
            if report.ok:
                return puzzle.model_copy(
                    update={"verify": report, "difficulty": self.difficulty(puzzle)}
                )
        raise GenerationError("cryptogram: could not build a uniquely solvable page")

    def solve(self, puzzle: Puzzle) -> SolveResult:
        counts = []
        for q in puzzle.data["quotes"]:
            words = [w for w in (normalize_word(x) for x in q["cipher"].split()) if w]
            n, done = count_decodings(words, dict(q["hints"]))
            counts.append(n if done else 2)
        return SolveResult(
            solved=all(c >= 1 for c in counts),
            solutions_found=max(counts) if counts else 0,
            stats={"quotes": float(len(counts))},
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        msgs: list[str] = []
        qs, sols = puzzle.data["quotes"], puzzle.solution["quotes"]
        if len(qs) != len(sols) or not qs:
            return VerifyReport(ok=False, unique=None, solver=SOLVER, messages=["quote count"])
        for i, (q, sol) in enumerate(zip(qs, sols, strict=True), 1):
            key: dict[str, str] = sol["key"]
            if any(k == v for k, v in key.items()):
                msgs.append(f"#{i}: a letter maps to itself")
            if len(set(key.values())) != len(key):
                msgs.append(f"#{i}: key is not one-to-one")
            if encipher(sol["plain"], key) != q["cipher"]:
                msgs.append(f"#{i}: cipher does not match plaintext under the key")
            inverse = {v: k for k, v in key.items()}
            for c, pch in q["hints"].items():
                if inverse.get(c) != pch:
                    msgs.append(f"#{i}: hint {c}={pch} is wrong")
            words = [w for w in (normalize_word(x) for x in q["cipher"].split()) if w]
            n, done = count_decodings(words, dict(q["hints"]))
            if not (n == 1 and done):
                msgs.append(f"#{i}: {n if done else '≥2?'} decodings fit the dictionary")
        plains = [normalize_word(s["plain"]) for s in sols]
        if len(set(plains)) != len(plains):
            msgs.append("the same quote appears twice on the page")
        ans = find_constraint(puzzle.spec, AnswerIs)
        if ans and not any(normalize_word(ans.word) in plain_words(s["plain"]) for s in sols):
            msgs.append("answer word not in the plaintext")
        return VerifyReport(
            ok=not msgs,
            unique=not any("decodings" in m for m in msgs),
            solver=SOLVER,
            messages=msgs,
        )

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        rows = []
        for q, sol in zip(puzzle.data["quotes"], puzzle.solution["quotes"], strict=True):
            n_letters = len(sol["key"])
            total = sum(len(w) for w in plain_words(sol["plain"]))
            rows.append((len(q["hints"]) / max(n_letters, 1), total, n_letters))
        k = len(rows)
        avg_letters = sum(r[1] for r in rows) / k
        hint_ratio = sum(r[0] for r in rows) / k
        f = {
            "avg_letters": round(avg_letters, 2),
            "hint_ratio": round(hint_ratio, 3),
            "distinct_letters": round(sum(r[2] for r in rows) / k, 2),
            "quotes": float(k),
        }
        # quote length separates the levels; hints are forced by uniqueness (≈ 0.5-0.6),
        # so they only nudge the score. Breakpoints fitted on 5-10 quote pages (2026-11-07).
        score = _interp(avg_letters, LETTERS_TO_SCORE) + 10 * (0.55 - hint_ratio)
        score = round(min(100.0, max(0.0, score)), 1)
        return DifficultyScore(score=score, label=level_from_score(score), features=f)

    def _block(self, puzzle: Puzzle, ctx: RenderCtx, solution: bool) -> list[dict[str, Any]]:
        large = bool(puzzle.data.get("large")) or ctx.large_print
        fpt = FONT_PT["large" if large else "normal"]
        if ctx.width_in < 5:  # solution cell: plain text list
            return [
                {
                    "kind": "paragraph",
                    "text": f"{i}. {s['plain']}" + (f" — {q['source']}" if q["source"] else ""),
                    "font_pt": 8.0,
                }
                for i, (q, s) in enumerate(
                    zip(puzzle.data["quotes"], puzzle.solution["quotes"], strict=True), 1
                )
            ]
        blocks: list[dict[str, Any]] = []
        for i, (q, sol) in enumerate(
            zip(puzzle.data["quotes"], puzzle.solution["quotes"], strict=True), 1
        ):
            inverse = {v: k for k, v in sol["key"].items()}
            words = []
            for cw in q["cipher"].split():
                cells = []
                for ch in cw:
                    if ch in ALPHA:
                        cells.append(
                            {"c": ch, "p": inverse[ch] if solution else q["hints"].get(ch, "")}
                        )
                    else:
                        cells.append({"c": "", "p": ch})
                words.append(cells)
            blocks.append(
                {
                    "kind": "cryptogram",
                    "number": i,
                    "words": words,
                    "font_pt": fpt,
                    "source": q["source"] if show_source(q["source"]) else "",
                }
            )
        return blocks

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        intro = {
            "kind": "paragraph",
            "text": "Each letter stands for another letter, and every quote has its own code. "
            "Some letters are given to get you started.",
        }
        return RenderedBlock(blocks=[intro, *self._block(puzzle, ctx, False)])

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(blocks=self._block(puzzle, ctx, True))
