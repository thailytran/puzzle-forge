"""Book Codes: 12 chars, no 0/O/1/I, last char = Luhn mod 32.

Identical to apps/casevault/casevault/bookcode.py (tests/vault/test_vault.py)."""

from __future__ import annotations

import re
import secrets

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
N = len(ALPHABET)
LENGTH = 12


def check_char(body: str) -> str:
    factor, total = 2, 0
    for ch in reversed(body):
        addend = factor * ALPHABET.index(ch)
        factor = 1 if factor == 2 else 2
        total += addend // N + addend % N
    return ALPHABET[(N - total % N) % N]


def new_code(rng: secrets.SystemRandom | None = None) -> str:
    r = rng or secrets.SystemRandom()
    body = "".join(r.choice(ALPHABET) for _ in range(LENGTH - 1))
    return body + check_char(body)


def canonical(text: str) -> str:
    t = re.sub(r"[\s\-_.]+", "", text).upper()
    return t


def is_valid(text: str) -> bool:
    t = canonical(text)
    if len(t) != LENGTH or any(ch not in ALPHABET for ch in t):
        return False
    return check_char(t[:-1]) == t[-1]


def pretty(code: str) -> str:
    t = canonical(code)
    return "-".join(t[i : i + 4] for i in range(0, len(t), 4))
