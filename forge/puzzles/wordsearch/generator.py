"""Word search generator (deterministic from seed)."""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, field

from forge.core.models import HiddenMessage, PuzzleSpec
from forge.puzzles.base import GenerationError, find_constraint
from forge.puzzles.wordsearch.grid import MASKED, Cell, cells_of, lines, make_mask, occurrences
from forge.puzzles.wordsearch.params import WsParams
from forge.wordlists import blocklist, normalize_word, theme_words

MIN_WORD_LEN = 3
MIN_WORDS_FLOOR = 5
COVERAGE = 0.6  # share of the theme words' letters we expect to land on fresh cells


@dataclass
class Draft:
    """Mutable grid under construction."""

    mask: list[list[bool]]
    grid: list[list[str | None]]
    placements: list[tuple[str, int, int, str]] = field(default_factory=list)
    word_cells: list[set[Cell]] = field(default_factory=list)
    message_cells: set[Cell] = field(default_factory=set)
    decoy_cells: set[Cell] = field(default_factory=set)

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0])

    def free_cells(self) -> list[Cell]:
        return [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.mask[r][c] and self.grid[r][c] is None
        ]

    def as_rows(self) -> list[str]:
        return [
            "".join(
                (ch if ch is not None else "?") if self.mask[r][c] else MASKED
                for c, ch in enumerate(row)
            )
            for r, row in enumerate(self.grid)
        ]


def word_pool(spec: PuzzleSpec) -> list[str]:
    """Normalized candidate words from the spec (explicit list, else built-in theme)."""
    raw = spec.words if spec.words else list(theme_words(spec.theme or "animals"))
    out: dict[str, None] = {}
    for w in raw:
        n = normalize_word(w)
        if len(n) >= MIN_WORD_LEN and n not in blocklist():
            out.setdefault(n, None)
    return list(out)


def _conflicts(word: str, chosen: list[str]) -> bool:
    """A word inside another (either way, either direction) would be found twice."""
    rev = word[::-1]
    return any(word in o or rev in o or o in word or o in rev for o in chosen)


def _candidates(d: Draft, word: str, dirs: tuple[str, ...]) -> list[tuple[int, int, str, int]]:
    out: list[tuple[int, int, str, int]] = []
    n = len(word)
    for r in range(d.rows):
        for c in range(d.cols):
            for dr in dirs:
                cells = cells_of(r, c, dr, n)
                overlap = 0
                ok = True
                for (rr, cc), ch in zip(cells, word, strict=True):
                    if not (0 <= rr < d.rows and 0 <= cc < d.cols) or not d.mask[rr][cc]:
                        ok = False
                        break
                    cur = d.grid[rr][cc]
                    if cur is None:
                        continue
                    if cur != ch or (rr, cc) in d.message_cells:
                        ok = False
                        break
                    overlap += 1
                if ok and overlap < n:
                    out.append((r, c, dr, overlap))
    return out


def _place(d: Draft, word: str, r: int, c: int, dr: str) -> None:
    cells = cells_of(r, c, dr, len(word))
    for (rr, cc), ch in zip(cells, word, strict=True):
        d.grid[rr][cc] = ch
    d.placements.append((word, r, c, dr))
    d.word_cells.append(set(cells))


def _try_place(
    d: Draft,
    word: str,
    p: WsParams,
    rng: random.Random,
    max_new_cells: int | None = None,
) -> bool:
    cands = _candidates(d, word, p.dirs)
    if max_new_cells is not None:
        cands = [x for x in cands if len(word) - x[3] <= max_new_cells]
    if not cands:
        return False
    if rng.random() < p.overlap_bias:
        best = max(x[3] for x in cands)
        cands = [x for x in cands if x[3] == best]
    r, c, dr, _ = cands[rng.randrange(len(cands))]
    _place(d, word, r, c, dr)
    return True


def _filler_letter(rng: random.Random, word_letters: str, bias: float) -> str:
    if word_letters and rng.random() < bias:
        return word_letters[rng.randrange(len(word_letters))]
    return string.ascii_uppercase[rng.randrange(26)]


def _blocked_spots(d: Draft) -> list[set[Cell]]:
    """Blocked words spelled anywhere that are not fully inside one placed word."""
    bad: list[set[Cell]] = []
    rows = d.as_rows()
    for _, text, cells in lines(rows):
        for b in blocklist():
            for target in (b, b[::-1]):
                i = text.find(target)
                while i != -1:
                    span = set(cells[i : i + len(b)])
                    if not any(span <= wc for wc in d.word_cells):
                        bad.append(span)
                    i = text.find(target, i + 1)
    return bad


def _duplicate_spots(d: Draft) -> list[set[Cell]]:
    """Accidental extra occurrences of a word (filler/decoys spelling it again)."""
    rows = d.as_rows()
    bad: list[set[Cell]] = []
    for (word, *_), placed in zip(d.placements, d.word_cells, strict=True):
        for r, c, dr in occurrences(rows, word):
            span = set(cells_of(r, c, dr, len(word)))
            if span != placed:
                bad.append(span)
    return bad


def build_draft(spec: PuzzleSpec, p: WsParams, rng: random.Random) -> Draft | None:
    """One attempt. Returns None when this random path cannot satisfy the spec."""
    hidden = find_constraint(spec, HiddenMessage)
    if hidden is not None:
        p = fit_size_for_message(p, word_pool(spec), len(normalize_word(hidden.text)))
    mask = make_mask(p.rows, p.cols, p.shape)
    d = Draft(mask=mask, grid=[[None] * p.cols for _ in range(p.rows)])
    max_len = max(p.rows, p.cols)
    pool = [w for w in word_pool(spec) if len(w) <= max_len]
    rng.shuffle(pool)
    target = rng.randint(p.min_words, p.max_words)
    if hidden is not None:
        target = len(pool)  # use every theme word we can before falling back to short words

    need = len(normalize_word(hidden.text)) if hidden is not None else 0
    chosen: list[str] = []
    for w in sorted(pool, key=len, reverse=True):
        if len(chosen) >= target:
            break
        if _conflicts(w, chosen):
            continue
        cap = len(d.free_cells()) - need if hidden is not None else None
        if _try_place(d, w, p, rng, max_new_cells=cap):
            chosen.append(w)
    # Loop ends early only when the target is reached; otherwise the pool is exhausted
    # (small theme, or nested words like RAPTOR/VELOCIRAPTOR) and we keep what fits.
    if len(chosen) < min(p.min_words, MIN_WORDS_FLOOR):
        return None

    if hidden is not None:
        if not _fit_message(d, normalize_word(hidden.text), chosen, pool, p, rng):
            return None
    else:
        _place_decoys(d, chosen, p, rng)

    letters = "".join(w for w, *_ in d.placements)
    fill_cells = d.free_cells()
    for r, c in fill_cells:
        d.grid[r][c] = _filler_letter(rng, letters, p.word_letter_fill)
    fillable = set(fill_cells) | d.decoy_cells
    for _ in range(200):
        spots = _blocked_spots(d) + _duplicate_spots(d)
        if not spots:
            return d
        for span in spots:
            changeable = sorted(span & fillable)
            if not changeable:
                return None  # spelled only by word/message letters: give up this attempt
            r, c = changeable[rng.randrange(len(changeable))]
            d.grid[r][c] = string.ascii_uppercase[rng.randrange(26)]
    return None


def _fit_message(
    d: Draft,
    message: str,
    chosen: list[str],
    pool: list[str],
    p: WsParams,
    rng: random.Random,
) -> bool:
    """Place extra words until exactly len(message) free cells remain, then write it."""
    need = len(message)
    if need == 0:
        return False
    extras = [w for w in pool if w not in chosen]
    extras += [w for w in theme_words("short_words") if w not in chosen and w not in extras]
    rng.shuffle(extras)
    free = len(d.free_cells())
    for w in extras:
        if free == need:
            break
        if free < need:
            return False
        if _conflicts(w, chosen):
            continue
        if _try_place(d, w, p, rng, max_new_cells=free - need):
            chosen.append(w)
            free = len(d.free_cells())
    if free != need:
        return False
    for (r, c), ch in zip(d.free_cells(), message, strict=True):
        d.grid[r][c] = ch
        d.message_cells.add((r, c))
    return True


def _place_decoys(d: Draft, chosen: list[str], p: WsParams, rng: random.Random) -> None:
    """Write partial words (e.g. OCTOPU for OCTOPUS) into free cells only."""
    longs = [w for w in chosen if len(w) >= 5]
    for _ in range(p.decoys):
        if not longs:
            return
        w = longs[rng.randrange(len(longs))]
        frag = w[: len(w) - rng.choice((1, 2))]
        spots: list[list[Cell]] = []
        for r in range(d.rows):
            for c in range(d.cols):
                for dr in p.dirs:
                    cells = cells_of(r, c, dr, len(frag))
                    if all(
                        0 <= rr < d.rows
                        and 0 <= cc < d.cols
                        and d.mask[rr][cc]
                        and d.grid[rr][cc] is None
                        for rr, cc in cells
                    ):
                        spots.append(cells)
        if not spots:
            return
        cells = spots[rng.randrange(len(spots))]
        for (rr, cc), ch in zip(cells, frag, strict=True):
            d.grid[rr][cc] = ch
            d.decoy_cells.add((rr, cc))


def fit_size_for_message(p: WsParams, pool: list[str], need: int) -> WsParams:
    """Shrink a square grid so the theme words can plausibly cover all but `need` cells."""
    from dataclasses import replace

    capacity = COVERAGE * sum(len(w) for w in pool) + need
    size = min(p.rows, p.cols)
    while size > 6 and size * size > capacity:
        size -= 1
    if size == min(p.rows, p.cols):
        return p
    return replace(p, rows=size, cols=size)


def require_words(spec: PuzzleSpec) -> None:
    if len(word_pool(spec)) < MIN_WORD_LEN:
        raise GenerationError("word search needs at least 3 usable words")
