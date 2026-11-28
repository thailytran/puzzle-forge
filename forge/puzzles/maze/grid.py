"""Maze cells as bitmasks of open passages + graph helpers (shared, generator-agnostic)."""

from __future__ import annotations

from collections import deque

N, E, S, W = 1, 2, 4, 8
DELTA = {N: (-1, 0), E: (0, 1), S: (1, 0), W: (0, -1)}
OPP = {N: S, S: N, E: W, W: E}

Cells = list[list[int]]
Cell = tuple[int, int]


def neighbors(cells: Cells, r: int, c: int) -> list[Cell]:
    rows, cols = len(cells), len(cells[0])
    out: list[Cell] = []
    for d, (dr, dc) in DELTA.items():
        rr, cc = r + dr, c + dc
        if cells[r][c] & d and 0 <= rr < rows and 0 <= cc < cols:
            out.append((rr, cc))
    return out


def bfs_path(cells: Cells, start: Cell, goal: Cell) -> list[Cell] | None:
    prev: dict[Cell, Cell | None] = {start: None}
    q: deque[Cell] = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            path: list[Cell] = []
            node: Cell | None = cur
            while node is not None:
                path.append(node)
                node = prev[node]
            return path[::-1]
        for nb in neighbors(cells, *cur):
            if nb not in prev:
                prev[nb] = cur
                q.append(nb)
    return None


def reachable(cells: Cells, start: Cell) -> int:
    seen = {start}
    q: deque[Cell] = deque([start])
    while q:
        for nb in neighbors(cells, *q.popleft()):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return len(seen)


def edge_count(cells: Cells) -> int:
    """Number of internal passages (each counted once)."""
    rows, cols = len(cells), len(cells[0])
    return sum(
        bool(cells[r][c] & E and c + 1 < cols) + bool(cells[r][c] & S and r + 1 < rows)
        for r in range(rows)
        for c in range(cols)
    )


def degree(cells: Cells, r: int, c: int) -> int:
    return len(neighbors(cells, r, c))


def dead_ends(cells: Cells) -> int:
    return sum(degree(cells, r, c) == 1 for r in range(len(cells)) for c in range(len(cells[0])))
