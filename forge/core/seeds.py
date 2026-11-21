"""Seed utilities. All randomness in generators must come from `make_rng`."""

from __future__ import annotations

import hashlib
import random

MAX_SEED = 2**63 - 1


def derive_seed(master: int, *parts: object) -> int:
    """Derive a child seed from a master seed and a path of labels.

    `derive_seed(book_seed, "page", 12)` is stable across Python versions and machines
    (unlike `hash()`). Parts are length-prefixed so ("a", "bc") != ("ab", "c").
    """
    h = hashlib.sha256()
    h.update(str(master).encode())
    for part in parts:
        b = repr(part).encode("utf-8")
        h.update(len(b).to_bytes(4, "big"))
        h.update(b)
    return int.from_bytes(h.digest()[:8], "big") & MAX_SEED


def make_rng(seed: int) -> random.Random:
    """Independent, reproducible RNG (Mersenne Twister, stable across CPython versions)."""
    return random.Random(seed)
