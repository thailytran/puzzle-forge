"""English dictionary (ENABLE, public domain) for uniqueness checks."""

from __future__ import annotations

import gzip
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from forge.wordlists import DATA_DIR

QUOTES_PATH = Path(__file__).parent / "quotes.txt"
EXTRA_WORDS = ("A", "I")  # ENABLE has no 1-letter words


@lru_cache(maxsize=1)
def words() -> frozenset[str]:
    with gzip.open(DATA_DIR / "enable1.txt.gz", "rt", encoding="ascii") as fh:
        out = {line.strip().upper() for line in fh if line.strip()}
    out.update(EXTRA_WORDS)
    return frozenset(out)


@lru_cache(maxsize=1)
def common_words() -> frozenset[str]:
    """Common English (SCOWL ≤ 35): what a puzzle solver would reasonably think of."""
    with gzip.open(DATA_DIR / "scowl35.txt.gz", "rt", encoding="utf-8") as fh:
        out = {line.strip().upper() for line in fh if line.strip()}
    out.update(EXTRA_WORDS)
    return frozenset(out)


def is_common(w: str) -> bool:
    return w.upper() in common_words()


def is_word(w: str) -> bool:
    return w.upper() in words()


@lru_cache(maxsize=1)
def _by_signature() -> dict[str, tuple[str, ...]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for w in words():
        groups["".join(sorted(w))].append(w)
    return {k: tuple(sorted(v)) for k, v in groups.items()}


def anagrams(w: str) -> tuple[str, ...]:
    """All dictionary words using exactly the letters of `w` (including `w` itself)."""
    return _by_signature().get("".join(sorted(w.upper())), ())


def pattern(w: str) -> str:
    """Letter-repetition pattern: HELLO → ABCCD."""
    seen: dict[str, str] = {}
    return "".join(seen.setdefault(ch, chr(65 + len(seen))) for ch in w)


@lru_cache(maxsize=1)
def by_pattern() -> dict[str, tuple[str, ...]]:
    """Common words grouped by letter pattern (cryptogram solver)."""
    groups: dict[str, list[str]] = defaultdict(list)
    for w in common_words():
        groups[pattern(w)].append(w)
    return {k: tuple(sorted(v)) for k, v in groups.items()}


def quotes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in QUOTES_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            text, _, source = line.partition("|")
            out.append((text.strip(), source.strip()))
    return out
