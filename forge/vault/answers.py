"""Answer normalisation + HMAC.

Must stay identical to apps/casevault/casevault/answers.py (tests/vault/test_vault.py)."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

KINDS = ("culprit_name", "unlock_code")


def normalize(kind: str, text: str) -> str:
    if kind == "unlock_code":
        return re.sub(r"[\s\-]+", "", text).upper()
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return "".join(ch for ch in t.casefold() if ch.isalnum())


def answer_hash(key: str, book_id: str, kind: str, text: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown answer kind {kind!r}")
    msg = f"{book_id}|{kind}|{normalize(kind, text)}".encode()
    return hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()


def code_hash(key: str, book_id: str, code: str) -> str:
    msg = f"{book_id}|book_code|{code}".encode()
    return hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()
