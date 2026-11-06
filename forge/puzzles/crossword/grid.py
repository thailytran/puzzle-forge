"""Crossword grid helpers: slots (maximal runs), numbering, fill-in solver."""

from __future__ import annotations

from dataclasses import dataclass

Rows = list[str]  # "#" = not a letter cell, letters otherwise
BLOCK = "#"


@dataclass(frozen=True)
class Slot:
    r: int
    c: int
    dir: str  # "A" across | "D" down
    length: int

    def cells(self) -> list[tuple[int, int]]:
        if self.dir == "A":
            return [(self.r, self.c + i) for i in range(self.length)]
        return [(self.r + i, self.c) for i in range(self.length)]


def slots(rows: Rows) -> list[Slot]:
    """Maximal runs of ≥ 2 letter cells, across then down, in reading order."""
    h, w = len(rows), len(rows[0])
    out: list[Slot] = []
    for r in range(h):
        for c in range(w):
            if rows[r][c] == BLOCK:
                continue
            if (c == 0 or rows[r][c - 1] == BLOCK) and c + 1 < w and rows[r][c + 1] != BLOCK:
                n = 0
                while c + n < w and rows[r][c + n] != BLOCK:
                    n += 1
                out.append(Slot(r, c, "A", n))
            if (r == 0 or rows[r - 1][c] == BLOCK) and r + 1 < h and rows[r + 1][c] != BLOCK:
                n = 0
                while r + n < h and rows[r + n][c] != BLOCK:
                    n += 1
                out.append(Slot(r, c, "D", n))
    return out


def numbering(rows: Rows) -> dict[tuple[int, int], int]:
    starts = sorted({(s.r, s.c) for s in slots(rows)})
    return {cell: i for i, cell in enumerate(starts, 1)}


def read(rows: Rows, s: Slot) -> str:
    return "".join(rows[r][c] for r, c in s.cells())


def count_fill_solutions(
    shape: Rows, words: list[str], givens: dict[tuple[int, int], str], limit: int = 2
) -> int:
    """Fill-in solver: place every word in exactly one slot so all crossings agree."""
    sl = slots(shape)
    if len(sl) != len(words):
        return 0
    letters: dict[tuple[int, int], str] = dict(givens)
    remaining = sorted(words)
    found = 0

    def options(s: Slot, pool: list[str]) -> list[str]:
        cells = s.cells()
        res = []
        for w in dict.fromkeys(pool):
            if len(w) == s.length and all(
                letters.get(cell, ch) == ch for cell, ch in zip(cells, w, strict=True)
            ):
                res.append(w)
        return res

    def rec(open_slots: list[Slot], pool: list[str]) -> bool:
        nonlocal found
        if not open_slots:
            found += 1
            return found >= limit
        best_i, best_opts = -1, None
        for i, s in enumerate(open_slots):
            o = options(s, pool)
            if not o:
                return False
            if best_opts is None or len(o) < len(best_opts):
                best_i, best_opts = i, o
                if len(o) == 1:
                    break
        assert best_opts is not None
        s = open_slots[best_i]
        rest = open_slots[:best_i] + open_slots[best_i + 1 :]
        for w in best_opts:
            added = [cell for cell in s.cells() if cell not in letters]
            for cell, ch in zip(s.cells(), w, strict=True):
                letters.setdefault(cell, ch)
            nxt = list(pool)
            nxt.remove(w)
            stop = rec(rest, nxt)
            for cell in added:
                del letters[cell]
            if stop:
                return True
        return False

    rec(sl, remaining)
    return found
