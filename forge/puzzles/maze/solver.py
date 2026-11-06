"""Independent maze verification: graph checks + BFS route."""

from __future__ import annotations

from forge.core.models import PathLetters, Puzzle, SolveResult, VerifyReport
from forge.puzzles.base import find_constraint
from forge.puzzles.maze.grid import DELTA, OPP, Cells, bfs_path, edge_count, reachable

SOLVER = "maze-bfs-v1"


def solve(puzzle: Puzzle) -> SolveResult:
    cells: Cells = [list(r) for r in puzzle.data["cells"]]
    start = tuple(puzzle.data["start"])
    goal = tuple(puzzle.data["goal"])
    path = bfs_path(cells, (start[0], start[1]), (goal[0], goal[1]))
    n = len(cells) * len(cells[0])
    unique = reachable(cells, (0, 0)) == n and edge_count(cells) == n - 1
    return SolveResult(
        solved=path is not None,
        solution={"path": [list(x) for x in path]} if path else None,
        solutions_found=1 if unique else 2,
    )


def verify(puzzle: Puzzle) -> VerifyReport:
    cells: Cells = [list(r) for r in puzzle.data["cells"]]
    rows, cols = len(cells), len(cells[0])
    msgs: list[str] = []
    for r in range(rows):
        for c in range(cols):
            for d, (dr, dc) in DELTA.items():
                rr, cc = r + dr, c + dc
                inside = 0 <= rr < rows and 0 <= cc < cols
                if cells[r][c] & d and not inside:
                    msgs.append(f"opening in the outer wall at ({r},{c})")
                if inside and bool(cells[r][c] & d) != bool(cells[rr][cc] & OPP[d]):
                    msgs.append(f"inconsistent wall between ({r},{c}) and ({rr},{cc})")
    res = solve(puzzle)
    if not res.solved:
        msgs.append("no route from start to finish")
    if res.solutions_found != 1:
        msgs.append("maze has loops or unreachable areas (route not unique)")
    if res.solution and res.solution["path"] != puzzle.solution["path"]:
        msgs.append("solver route differs from stored route")
    pl = find_constraint(puzzle.spec, PathLetters)
    if pl is not None and res.solution:
        letters = {(x["r"], x["c"]): x["ch"] for x in puzzle.data["letters"]}
        got = "".join(letters.get((r, c), "") for r, c in res.solution["path"])
        want = "".join(ch for ch in pl.seq.upper() if ch.isalnum())
        if got != want:
            msgs.append(f"letters on the route read {got!r}, expected {want!r}")
    return VerifyReport(
        ok=not msgs, unique=res.solutions_found == 1, solver=SOLVER, messages=msgs[:10]
    )
