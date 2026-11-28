"""Grid geometry shared by generator and solver (no generator state here)."""

from __future__ import annotations

from collections.abc import Iterator

from forge.puzzles.wordsearch.params import DIRS

Cell = tuple[int, int]
MASKED = "."


def make_mask(rows: int, cols: int, shape: str) -> list[list[bool]]:
    """True = active cell. Shapes: rect, circle, diamond."""
    cr, cc = (rows - 1) / 2, (cols - 1) / 2
    out: list[list[bool]] = []
    for r in range(rows):
        row: list[bool] = []
        for c in range(cols):
            dr, dc = (r - cr) / (rows / 2), (c - cc) / (cols / 2)
            if shape == "rect":
                row.append(True)
            elif shape == "circle":
                row.append(dr * dr + dc * dc <= 1.0)
            elif shape == "diamond":
                row.append(abs(dr) + abs(dc) <= 1.05)
            else:
                raise ValueError(f"unknown shape {shape!r} (rect | circle | diamond)")
        out.append(row)
    return out


def cells_of(r: int, c: int, d: str, length: int) -> list[Cell]:
    dr, dc = DIRS[d]
    return [(r + i * dr, c + i * dc) for i in range(length)]


OPPOSITE = {"E": "W", "W": "E", "S": "N", "N": "S", "SE": "NW", "NW": "SE", "NE": "SW", "SW": "NE"}


def lines(rows: list[str]) -> Iterator[tuple[str, str, list[Cell]]]:
    """Every maximal straight line in the 4 forward directions: (dir, text, cells)."""
    nr, nc = len(rows), len(rows[0])
    starts: dict[str, list[Cell]] = {
        "E": [(r, 0) for r in range(nr)],
        "S": [(0, c) for c in range(nc)],
        "SE": [(r, 0) for r in range(nr)] + [(0, c) for c in range(1, nc)],
        "NE": [(r, 0) for r in range(nr)] + [(nr - 1, c) for c in range(1, nc)],
    }
    for d, ss in starts.items():
        dr, dc = DIRS[d]
        for r0, c0 in ss:
            cells: list[Cell] = []
            r, c = r0, c0
            while 0 <= r < nr and 0 <= c < nc:
                cells.append((r, c))
                r, c = r + dr, c + dc
            yield d, "".join(rows[r][c] for r, c in cells), cells


Placement = tuple[int, int, str]  # (row, col, direction) of the first letter


def occurrences(rows: list[str], word: str) -> list[Placement]:
    """Every distinct placement of `word` (8 directions). Palindromes count once."""
    seen: set[frozenset[Cell]] = set()
    out: list[Placement] = []
    n = len(word)
    for d, text, cells in lines(rows):
        for target, reverse in ((word, False), (word[::-1], True)):
            start = text.find(target)
            while start != -1:
                span = cells[start : start + n]
                key = frozenset(span)
                if key not in seen:
                    seen.add(key)
                    r, c = span[-1] if reverse else span[0]
                    out.append((r, c, OPPOSITE[d] if reverse else d))
                start = text.find(target, start + 1)
    return sorted(out)
