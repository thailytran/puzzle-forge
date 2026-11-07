"""Second, independent solvers for QA L1.dual_solver.

Each uses a *different algorithm* from the generator and from the type's own `verify` solver:
- sudoku 9x9: rustoku vs our Python MRV backtracking; 4x4/6x6: row-permutation search
- word search: naive cell-by-direction character scan (verify uses line strings + str.find)
- maze: recursive DFS enumerating simple routes (verify uses BFS + tree check)
- scramble: length-filtered dictionary scan with Counter equality (verify uses a signature index)
- crossword fill-in: fixed-order slot backtracking (verify uses MRV)
- cryptogram: letter-level backtracking with forward checking (verify is word-level)

Every function returns (solutions_found ≤ 2, canonical solution or None).
"""

from __future__ import annotations

import functools
import itertools
import sys
from collections import Counter
from typing import Any

from forge.core.models import Puzzle

Result = tuple[int, Any]


def sudoku(p: Puzzle) -> Result:
    givens = [list(r) for r in p.data["givens"]]
    n = len(givens)
    if n == 9:
        import rustoku

        s = "".join(str(v) for row in givens for v in row)
        count = int(rustoku.count_solutions(s, 2))
        sol = rustoku.solve(s)
        grid = [[int(sol[r * 9 + c]) for c in range(9)] for r in range(9)] if sol else None
        return count, grid
    from forge.puzzles.sudoku.grid import box_shape

    br, bc = box_shape(n)
    perms = list(itertools.permutations(range(1, n + 1)))
    found: list[list[tuple[int, ...]]] = []

    def ok(rows: list[tuple[int, ...]]) -> bool:
        r = len(rows) - 1
        row = rows[r]
        if any(givens[r][c] and givens[r][c] != row[c] for c in range(n)):
            return False
        for c in range(n):
            if any(rows[i][c] == row[c] for i in range(r)):
                return False
        b0 = r - r % br
        for c0 in range(0, n, bc):
            seen = [rows[i][c] for i in range(b0, r + 1) for c in range(c0, c0 + bc)]
            if len(seen) != len(set(seen)):
                return False
        return True

    def rec(rows: list[tuple[int, ...]]) -> bool:
        if len(rows) == n:
            found.append(list(rows))
            return len(found) >= 2
        for perm in perms:
            rows.append(perm)
            if ok(rows) and rec(rows):
                return True
            rows.pop()
        return False

    rec([])
    return len(found), [list(r) for r in found[0]] if found else None


def wordsearch(p: Puzzle) -> Result:
    rows: list[str] = p.data["rows"]
    h, w = len(rows), len(rows[0])
    dirs = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
    placements: dict[str, set[frozenset[tuple[int, int]]]] = {}
    for word in p.data["words"]:
        spots: set[frozenset[tuple[int, int]]] = set()
        for r in range(h):
            for c in range(w):
                for dr, dc in dirs:
                    cells = [(r + i * dr, c + i * dc) for i in range(len(word))]
                    if all(
                        0 <= rr < h and 0 <= cc < w and rows[rr][cc] == ch
                        for (rr, cc), ch in zip(cells, word, strict=True)
                    ):
                        spots.add(frozenset(cells))
        placements[word] = spots
    worst = max((len(s) for s in placements.values()), default=0)
    canon = {w_: sorted(sorted(s) for s in spots) for w_, spots in placements.items()}
    return (
        1 if worst == 1 and all(placements.values()) else (0 if not all(placements.values()) else 2)
    ), canon


def maze(p: Puzzle) -> Result:
    from forge.puzzles.maze.grid import neighbors

    cells = [list(r) for r in p.data["cells"]]
    start, goal = tuple(p.data["start"]), tuple(p.data["goal"])
    routes: list[list[tuple[int, int]]] = []
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, len(cells) * len(cells[0]) + 500))
    try:

        def dfs(
            node: tuple[int, int], path: list[tuple[int, int]], seen: set[tuple[int, int]]
        ) -> bool:
            if node == goal:
                routes.append(list(path))
                return len(routes) >= 2
            for nb in neighbors(cells, *node):
                if nb not in seen:
                    seen.add(nb)
                    path.append(nb)
                    if dfs(nb, path, seen):
                        return True
                    path.pop()
                    seen.discard(nb)
            return False

        s = (start[0], start[1])
        dfs(s, [s], {s})
    finally:
        sys.setrecursionlimit(limit)
    return len(routes), [list(x) for x in routes[0]] if routes else None


@functools.lru_cache(maxsize=1)
def _dict_by_len() -> dict[int, tuple[str, ...]]:
    from forge.wordlists.dictionary import words

    out: dict[int, list[str]] = {}
    for w in words():
        out.setdefault(len(w), []).append(w)
    return {k: tuple(v) for k, v in out.items()}


def scramble(p: Puzzle) -> Result:
    bank = set(p.data["word_bank"])
    items = list(p.data["items"]) + ([p.data["bonus"]] if p.data.get("bonus") else [])
    answers: list[list[str]] = []
    for s in items:
        want = Counter(s)
        pool = set(_dict_by_len().get(len(s), ())) | {w for w in bank if len(w) == len(s)}
        answers.append(sorted(w for w in pool if Counter(w) == want))
    count = 1 if all(len(a) == 1 for a in answers) else (0 if not all(answers) else 2)
    return count, [a[0] for a in answers] if count == 1 else None


def crossword(p: Puzzle) -> Result:
    from forge.puzzles.crossword.grid import slots

    shape: list[str] = p.data["shape"]
    sl = slots(shape)
    givens = {tuple(map(int, k.split(","))): v for k, v in p.data["givens"].items()}
    words = list(p.data["words"])
    letters: dict[tuple[int, int], str] = dict(givens)  # type: ignore[arg-type]
    sols: list[dict[tuple[int, int], str]] = []

    def rec(i: int, pool: list[str]) -> bool:
        if i == len(sl):
            sols.append(dict(letters))
            return len(sols) >= 2
        s = sl[i]
        for w in sorted(set(pool)):
            if len(w) != s.length:
                continue
            cells = s.cells()
            if any(letters.get(c, ch) != ch for c, ch in zip(cells, w, strict=True)):
                continue
            added = [c for c in cells if c not in letters]
            for c, ch in zip(cells, w, strict=True):
                letters.setdefault(c, ch)
            nxt = list(pool)
            nxt.remove(w)
            stop = rec(i + 1, nxt)
            for c in added:
                del letters[c]
            if stop:
                return True
        return False

    if len(sl) == len(words):
        rec(0, words)
    if not sols:
        return 0, None
    h, w = len(shape), len(shape[0])
    rows = ["".join(sols[0].get((r, c), "#") for c in range(w)) for r in range(h)]
    return len(sols), rows


def _crypto_one(cipher: str, hints: dict[str, str]) -> Result:
    from forge.puzzles.cryptogram import plain_words
    from forge.wordlists.dictionary import by_pattern, pattern

    cipher_words = sorted(set(plain_words(cipher)))
    cands = {cw: list(by_pattern().get(pattern(cw), ())) for cw in cipher_words}
    letters = sorted(
        {ch for cw in cipher_words for ch in cw if ch not in hints},
        key=lambda ch: -sum(cw.count(ch) for cw in cipher_words),
    )
    sols: list[dict[str, str]] = []
    budget = [400_000]

    def consistent(m: dict[str, str]) -> bool:
        for cw in cipher_words:
            if not any(
                all(m.get(c, pw[i]) == pw[i] and c != pw[i] for i, c in enumerate(cw))
                for pw in cands[cw]
            ):
                return False
        return True

    def rec(i: int, m: dict[str, str], used: set[str]) -> bool:
        budget[0] -= 1
        if budget[0] < 0:
            return True
        if i == len(letters):
            if all("".join(m[c] for c in cw) in cands[cw] for cw in cipher_words):
                sols.append(dict(m))
            return len(sols) >= 2
        c = letters[i]
        for pch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if pch in used or pch == c:
                continue
            m[c] = pch
            used.add(pch)
            if consistent(m) and rec(i + 1, m, used):
                return True
            del m[c]
            used.discard(pch)
        return False

    base = dict(hints)
    if consistent(base):
        rec(0, base, set(base.values()))
    if budget[0] < 0:
        return 2, None  # could not prove uniqueness in budget → treat as not unique
    if not sols:
        return 0, None
    return len(sols), "".join(sols[0].get(ch, ch) for ch in cipher)


def cryptogram(p: Puzzle) -> Result:
    """Letter-level backtracking per quote (verify uses word-level search)."""
    worst, plains = 1, []
    for q in p.data["quotes"]:
        n, plain = _crypto_one(q["cipher"], dict(q["hints"]))
        worst = n if n != 1 else worst
        plains.append(plain)
    return worst, plains if worst == 1 else None


SOLVERS = {
    "sudoku": sudoku,
    "wordsearch": wordsearch,
    "maze": maze,
    "scramble": scramble,
    "crossword": crossword,
    "cryptogram": cryptogram,
}


def matches_stored(p: Puzzle, solution: Any) -> bool:
    """Compare a second-solver solution with what the generator stored."""
    t = p.type
    if t == "sudoku":
        return bool(solution == p.solution["grid"])
    if t == "wordsearch":
        from forge.puzzles.wordsearch.grid import cells_of

        stored = {
            pl["word"]: [sorted(cells_of(pl["row"], pl["col"], pl["dir"], len(pl["word"])))]
            for pl in p.solution["placements"]
        }
        return bool(solution == stored)
    if t == "maze":
        return bool(solution == p.solution["path"])
    if t == "scramble":
        want = list(p.solution["answers"]) + (
            [p.solution["bonus"]] if p.solution.get("bonus") else []
        )
        return bool(solution == want)
    if t == "crossword":
        return bool(solution == p.solution["rows"])
    if t == "cryptogram":
        return bool(solution == [q["plain"] for q in p.solution["quotes"]])
    return False
