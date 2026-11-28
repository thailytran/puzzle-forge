"""Independent word search solver: only reads the printed grid + word list."""

from __future__ import annotations

import string
from typing import Any

from forge.core.models import HiddenMessage, Puzzle, SolveResult, VerifyReport
from forge.puzzles.base import find_constraint
from forge.puzzles.wordsearch.grid import MASKED, Cell, cells_of, lines, occurrences
from forge.wordlists import blocklist, normalize_word

SOLVER = "wordsearch-scan-v1"


def solve_grid(rows: list[str], words: list[str]) -> SolveResult:
    placements: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    covered: set[Cell] = set()
    for w in words:
        occ = occurrences(rows, w)
        counts[w] = len(occ)
        for r, c, d in occ:
            placements.append({"word": w, "row": r, "col": c, "dir": d})
            covered.update(cells_of(r, c, d, len(w)))
    leftover = "".join(
        ch
        for r, row in enumerate(rows)
        for c, ch in enumerate(row)
        if ch != MASKED and (r, c) not in covered
    )
    solved = all(n >= 1 for n in counts.values())
    unique = all(n == 1 for n in counts.values())
    return SolveResult(
        solved=solved,
        solution={"placements": placements, "leftover": leftover, "counts": counts},
        solutions_found=1 if unique else 2,
        stats={"words": float(len(words))},
    )


def solve(puzzle: Puzzle) -> SolveResult:
    return solve_grid(list(puzzle.data["rows"]), list(puzzle.data["words"]))


def _filler_blocked(rows: list[str], word_cells: list[set[Cell]]) -> list[str]:
    hits: list[str] = []
    for _, text, cells in lines(rows):
        for b in blocklist():
            for target in (b, b[::-1]):
                i = text.find(target)
                while i != -1:
                    span = set(cells[i : i + len(b)])
                    if not any(span <= wc for wc in word_cells):
                        hits.append(b)
                    i = text.find(target, i + 1)
    return hits


def verify(puzzle: Puzzle) -> VerifyReport:
    rows: list[str] = list(puzzle.data["rows"])
    msgs: list[str] = []
    width = len(rows[0]) if rows else 0
    if not rows or any(len(r) != width for r in rows):
        return VerifyReport(ok=False, unique=None, solver=SOLVER, messages=["grid not rectangular"])
    allowed = set(string.ascii_uppercase) | {MASKED}
    if any(ch not in allowed for row in rows for ch in row):
        msgs.append("grid contains characters other than A-Z")
    res = solve(puzzle)
    sol = res.solution or {}
    counts: dict[str, int] = sol.get("counts", {})
    for w, n in counts.items():
        if n != 1:
            msgs.append(f"{w} found {n} times")
    expected = {
        (p["word"], p["row"], p["col"], p["dir"]) for p in puzzle.solution.get("placements", [])
    }
    found = {(p["word"], p["row"], p["col"], p["dir"]) for p in sol.get("placements", [])}
    if res.solutions_found == 1 and expected != found:
        msgs.append("solver placements differ from generator placements")
    allowed_dirs = set(puzzle.data.get("directions", []))
    if allowed_dirs and any(p[3] not in allowed_dirs for p in found):
        msgs.append("a word runs in a direction not allowed for this level")
    word_cells = [set(cells_of(p[1], p[2], p[3], len(p[0]))) for p in found]
    blocked = _filler_blocked(rows, word_cells)
    if blocked:
        msgs.append(f"blocked word in filler: {sorted(set(blocked))}")
    hidden = find_constraint(puzzle.spec, HiddenMessage)
    if hidden is not None and sol.get("leftover") != normalize_word(hidden.text):
        msgs.append(f"leftover letters {sol.get('leftover')!r} != hidden message")
    return VerifyReport(
        ok=res.solved and not msgs,
        unique=res.solutions_found == 1,
        solver=SOLVER,
        messages=msgs,
    )
