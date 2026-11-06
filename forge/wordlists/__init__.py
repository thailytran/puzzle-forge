"""Built-in theme word lists and the content blocklist.

These hand-written lists are kid-safe. AI expansion + LLM safety check arrive in P2.2.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
BLOCKLIST_PATH = Path(__file__).parent / "blocklist.txt"


def normalize_word(word: str) -> str:
    """Uppercase A-Z only: "sea horse" → "SEAHORSE", "T-Rex" → "TREX"."""
    return re.sub(r"[^A-Z]", "", word.upper())


@lru_cache(maxsize=1)
def blocklist() -> frozenset[str]:
    words = set()
    for line in BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.add(normalize_word(line))
    return frozenset(words)


def is_blocked(word: str) -> bool:
    return normalize_word(word) in blocklist()


def available_themes() -> list[str]:
    return sorted(p.stem for p in DATA_DIR.glob("*.txt"))


def theme_key(theme: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", theme.lower()).strip("_")


@lru_cache(maxsize=64)
def theme_words(theme: str) -> tuple[str, ...]:
    """Normalized, deduplicated, blocklist-filtered words for a built-in theme."""
    path = DATA_DIR / f"{theme_key(theme)}.txt"
    if not path.is_file():
        raise KeyError(f"unknown theme {theme!r}; built-in themes: {', '.join(available_themes())}")
    seen: dict[str, None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        w = normalize_word(line)
        if w and not is_blocked(w):
            seen.setdefault(w, None)
    return tuple(seen)
