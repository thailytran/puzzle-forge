# ruff: noqa: E501  (SVG path strings read better on one line)
"""Pigpen cipher: every letter is drawn as the outline of its pen in the key (two grids and two
crosses, the second of each with dots). The key is printed with the puzzle, so the reading is
always unique; the puzzle is the decoding. Mystery use: the message carries the keyword
(`answer_is` = the word to write on the keyword line).

Glyphs are stored as shape codes (pen + dot); the solver rebuilds the key from geometry alone and
decodes. Glyph pictures are SVG files drawn here (like the maze).
"""

from __future__ import annotations

import hashlib
import re

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
from forge.puzzles.base import GenerationError, find_constraint

SOLVER = "pigpen-geometry-key-v1"
HOW = "Every symbol is the shape of its letter's pen in the key. Decode the message, then write the keyword."
# pen of a grid letter: which sides of its cell are drawn (top, right, bottom, left)
GRID_SIDES = [
    (0, 1, 1, 0),
    (0, 1, 1, 1),
    (0, 0, 1, 1),
    (1, 1, 1, 0),
    (1, 1, 1, 1),
    (1, 0, 1, 1),
    (1, 1, 0, 0),
    (1, 1, 0, 1),
    (1, 0, 0, 1),
]
X_SIDES = ["v-down", "v-left", "v-right", "v-up"]  # opening of the V: top, right, left, bottom arms


def _key() -> dict[str, tuple[str, int, bool]]:
    """Letter -> (shape kind, index, dot). A-I grid, J-R grid+dot, S-V cross, W-Z cross+dot."""
    out: dict[str, tuple[str, int, bool]] = {}
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(9):
        out[letters[i]] = ("grid", i, False)
        out[letters[9 + i]] = ("grid", i, True)
    for i in range(4):
        out[letters[18 + i]] = ("x", i, False)
        out[letters[22 + i]] = ("x", i, True)
    return out


def code_of(ch: str) -> str:
    kind, i, dot = _key()[ch]
    return f"{kind}{i}{'d' if dot else ''}"


def decode(codes: list[str]) -> str:
    """Independent decoding: rebuild the key from the pen geometry (grid cells read left to right,
    top to bottom; crosses top, right, left, bottom) and look every symbol up."""
    table: dict[str, str] = {}
    alphabet = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    for dot in (False, True):
        for i in range(len(GRID_SIDES)):
            table[f"grid{i}{'d' if dot else ''}"] = next(alphabet)
    for dot in (False, True):
        for i in range(len(X_SIDES)):
            table[f"x{i}{'d' if dot else ''}"] = next(alphabet)
    return "".join(table.get(c, " ") if c != " " else " " for c in codes)


def _glyph(code: str, x: float, y: float, s: float) -> str:
    """SVG of one symbol in a box of size s at (x, y)."""
    dot = code.endswith("d")
    i = int(code.rstrip("d")[-1])
    p = []
    if code.startswith("grid"):
        t, r, b, lft = GRID_SIDES[i]
        if t:
            p.append(f"M{x},{y} L{x + s},{y}")
        if r:
            p.append(f"M{x + s},{y} L{x + s},{y + s}")
        if b:
            p.append(f"M{x},{y + s} L{x + s},{y + s}")
        if lft:
            p.append(f"M{x},{y} L{x},{y + s}")
    else:
        cx, cy = x + s / 2, y + s / 2
        arms = {  # V shapes of the cross: the letter sits in the opening
            0: f"M{x},{y} L{cx},{cy} L{x + s},{y}",
            1: f"M{x + s},{y} L{cx},{cy} L{x + s},{y + s}",
            2: f"M{x},{y} L{cx},{cy} L{x},{y + s}",
            3: f"M{x},{y + s} L{cx},{cy} L{x + s},{y + s}",
        }
        p.append(arms[i])
    out = f'<path d="{" ".join(p)}" stroke="#111" stroke-width="{s * 0.09:.2f}" fill="none" stroke-linecap="square"/>'
    if dot:
        if code.startswith("grid"):
            dx, dy = x + s / 2, y + s / 2
        else:
            dx, dy = {
                0: (x + s / 2, y + s * 0.22),
                1: (x + s * 0.78, y + s / 2),
                2: (x + s * 0.22, y + s / 2),
                3: (x + s / 2, y + s * 0.78),
            }[i]
        out += f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="{s * 0.08:.1f}" fill="#111"/>'
    return out


def message_svg(codes: list[str], per_line: int = 14, s: float = 40) -> str:
    gap = s * 0.45
    words, line, lines = [], [], []
    for c in [*codes, " "]:
        if c == " ":
            if line:
                words.append(line)
            line = []
        else:
            line.append(c)
    cur: list[list[str]] = []
    for w in words:
        if sum(len(x) + 1 for x in cur) + len(w) > per_line and cur:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    body, width = [], 0.0
    for li, ws in enumerate(lines):
        x = 0.0
        y = li * s * 1.9
        for w in ws:
            for c in w:
                body.append(_glyph(c, x + 4, y + 4, s))
                x += s + gap
            x += s * 0.9
        width = max(width, x)
    h = len(lines) * s * 1.9
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 8:.0f}" height="{h + 8:.0f}">{"".join(body)}</svg>'


def key_svg(s: float = 34) -> str:
    """The key: grid A-I, grid with dots J-R, cross S-V, cross with dots W-Z, letters in the pens."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    for g, ox in ((0, 0), (1, 3.6 * s)):
        for i in range(9):
            r, c = divmod(i, 3)
            out.append(_glyph(f"grid{i}{'d' if g else ''}", ox + c * s, r * s, s))
            # dotted grid: small letter in the corner, the dot keeps the centre
            lx, ly, fs = (0.3, 0.72, 0.42) if not g else (0.1, 0.4, 0.32)
            out.append(
                f'<text x="{ox + c * s + s * lx:.0f}" y="{r * s + s * ly:.0f}" font-size="{s * fs:.0f}" '
                f'font-family="sans-serif" fill="#a0322c">{letters[g * 9 + i]}</text>'
            )
    for g, ox in ((0, 7.4 * s), (1, 10.6 * s)):
        for i in range(4):
            out.append(_glyph(f"x{i}{'d' if g else ''}", ox, s * 0.5, 2 * s))
        lab = letters[18 + g * 4 : 22 + g * 4]
        pos = [
            (ox + s * 0.85, s * 0.95),
            (ox + s * 1.55, s * 1.65),
            (ox + s * 0.2, s * 1.65),
            (ox + s * 0.85, s * 2.35),
        ]
        if g:  # dotted cross: letters beside the dots, not on them
            pos = [
                (ox + s * 1.2, s * 0.92),
                (ox + s * 1.6, s * 1.32),
                (ox + s * 0.1, s * 1.32),
                (ox + s * 1.2, s * 2.42),
            ]
        for ch, (lx, ly) in zip(lab, pos, strict=True):
            out.append(
                f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="{s * 0.42:.0f}" font-family="sans-serif" fill="#a0322c">{ch}</text>'
            )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{12.8 * s:.0f}" height="{3.2 * s:.0f}">{"".join(out)}</svg>'


class Pigpen:
    name = "pigpen"

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle:
        ans = find_constraint(spec, AnswerIs)
        text = str(spec.options.get("text") or "")
        word = ans.word.upper() if ans else ""
        if not text:
            text = f"THE WORD YOU NEED IS {word}" if word else "LOOK UNDER THE OLD BRIDGE"
        msg = re.sub(r"[^A-Z ]", "", text.upper())
        msg = re.sub(r" +", " ", msg).strip()
        if word and word not in msg.split():
            raise GenerationError(f"pigpen: the message must contain the keyword {word!r}")
        codes = [" " if ch == " " else code_of(ch) for ch in msg]
        puzzle = build_puzzle(
            spec,
            seed,
            data={"codes": codes},
            solution={"text": msg, "word": word or msg.split()[-1]},
            token=word or msg.split()[-1],
        )
        rep = self.verify(puzzle)
        if not rep.ok:
            raise GenerationError(f"pigpen failed verification: {rep.messages}")
        return puzzle.model_copy(update={"verify": rep, "difficulty": self.difficulty(puzzle)})

    def solve(self, puzzle: Puzzle) -> SolveResult:
        text = decode(puzzle.data["codes"])
        return SolveResult(
            solved=True, solution={"text": text, "word": puzzle.solution["word"]}, solutions_found=1
        )

    def verify(self, puzzle: Puzzle) -> VerifyReport:
        res = self.solve(puzzle)
        msgs = (
            []
            if res.solution and res.solution["text"] == puzzle.solution["text"]
            else ["decoded text differs"]
        )
        if puzzle.solution["word"] not in puzzle.solution["text"].split():
            msgs.append("keyword is not a word of the message")
        return VerifyReport(ok=not msgs, unique=True, solver=SOLVER, messages=msgs)

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore:
        n = sum(1 for c in puzzle.data["codes"] if c != " ")
        score = round(min(60.0, 8 + n * 1.2), 1)
        return DifficultyScore(
            score=score, label=level_from_score(score), features={"letters": float(n)}
        )

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        msg = message_svg(puzzle.data["codes"])
        key = key_svg()
        h = hashlib.sha1(msg.encode()).hexdigest()[:16]
        files = {f"img/pigpen-{h}.svg": msg.encode(), "img/pigpen-key.svg": key.encode()}
        w = min(ctx.width_in, 5.6)
        return RenderedBlock(
            blocks=[
                {"kind": "paragraph", "text": HOW},
                {"kind": "image", "path": "img/pigpen-key.svg", "width_in": round(w * 0.9, 2)},
                {"kind": "spacer", "height_in": 0.2},
                {"kind": "image", "path": f"img/pigpen-{h}.svg", "width_in": round(w, 2)},
            ],
            files=files,
        )

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:
        return RenderedBlock(
            blocks=[{"kind": "paragraph", "text": f"Message: {puzzle.solution['text']}"}]
        )


__all__ = ["Level", "Pigpen", "decode"]
