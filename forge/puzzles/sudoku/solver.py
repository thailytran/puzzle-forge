"""Sudoku verification with the independent pure-Python solver (+ rustoku cross-check)."""

from __future__ import annotations

import rustoku

from forge.core.models import Puzzle, ShadedCells, SolveResult, VerifyReport
from forge.puzzles.base import find_constraint
from forge.puzzles.sudoku.grid import (
    Grid,
    box_shape,
    count_solutions,
    is_valid_complete,
    to_string,
)
from forge.puzzles.sudoku.grid import (
    solve as py_solve,
)

SOLVER = "sudoku-backtrack-py-v1"


def solve(puzzle: Puzzle) -> SolveResult:
    givens: Grid = [list(row) for row in puzzle.data["givens"]]
    n_solutions = count_solutions(givens, 2)
    sol = py_solve(givens)
    return SolveResult(
        solved=sol is not None,
        solution={"grid": sol} if sol else None,
        solutions_found=n_solutions,
    )


def verify(puzzle: Puzzle) -> VerifyReport:
    msgs: list[str] = []
    n = int(puzzle.data["size"])
    givens: Grid = [list(row) for row in puzzle.data["givens"]]
    try:
        box_shape(n)
    except ValueError as exc:
        return VerifyReport(ok=False, unique=None, solver=SOLVER, messages=[str(exc)])
    if len(givens) != n or any(len(r) != n for r in givens):
        return VerifyReport(ok=False, unique=None, solver=SOLVER, messages=["bad grid shape"])
    res = solve(puzzle)
    unique = res.solutions_found == 1
    if not res.solved:
        msgs.append("no solution")
    elif not unique:
        msgs.append("more than one solution")
    expected: Grid = puzzle.solution.get("grid", [])
    if res.solution and res.solution["grid"] != expected:
        msgs.append("solver solution differs from stored solution")
    if expected and not is_valid_complete([list(r) for r in expected]):
        msgs.append("stored solution is not a valid sudoku")
    if any(givens[r][c] not in (0, expected[r][c]) for r in range(n) for c in range(n)):
        msgs.append("givens disagree with stored solution")
    if n == 9 and unique:
        cross = rustoku.solve(to_string(givens))
        if cross != to_string(expected):
            msgs.append("rustoku cross-check disagrees")
    sc = find_constraint(puzzle.spec, ShadedCells)
    if sc is not None and expected:
        got = "".join(str(expected[r][c]) for r, c in sc.cells)
        if got != "".join(ch for ch in sc.expect if ch.isdigit()):
            msgs.append(f"shaded cells read {got!r}, expected {sc.expect!r}")
        if any(givens[r][c] for r, c in sc.cells):
            msgs.append("a shaded cell is given (reader would not need to solve it)")
    return VerifyReport(ok=not msgs, unique=unique, solver=SOLVER, messages=msgs)
