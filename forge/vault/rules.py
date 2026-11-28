"""Rules that tie a book's final answer to the CaseVault website (MYSTERY_DESIGN.md section 17).

Pure functions returning human-readable problems (empty list = OK). Used by `forge mystery check`
(case frame) and by the vault payload builder (a book that breaks them is never registered)."""

from __future__ import annotations

import re
from typing import Any

from forge.vault.answers import normalize

TRIVIAL_CODES = re.compile(r"^(\d)\1+$|^0123|^1234|^2345|^3456|^4567|^5678|^6789|^9876|^4321")
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{3,7}$")


def answer_problems(
    answer_type: str,
    culprit: list[str],
    codes: list[str],
    suspects: list[str] | None = None,
    kids: bool = False,
) -> list[str]:
    """R1-R4: one clear final answer, typed the way the website accepts it."""
    p: list[str] = []
    kinds = ["culprit_name", "unlock_code"] if answer_type == "both" else [answer_type]
    if "culprit_name" in kinds:
        if not culprit:
            p.append("R1 culprit_name: at least one accepted spelling is needed")
        canon = culprit[0] if culprit else ""
        for v in culprit:
            n = normalize("culprit_name", v)
            if not n:
                p.append(f"R2 culprit_name {v!r} has no letters or digits")
            if kids and len(n) > 14:
                p.append(f"R4 kids: {v!r} is too long to type ({len(n)} letters, max 14)")
        if suspects:
            sus = {normalize("culprit_name", s): s for s in suspects}
            if canon and normalize("culprit_name", canon) not in sus:
                p.append(f"R2 culprit {canon!r} is not printed as a suspect name in the book")
            for v in culprit[1:]:  # a short variant (surname) must not fit another suspect too
                nv = normalize("culprit_name", v)
                hits = [
                    s
                    for k, s in sus.items()
                    if nv and (k == nv or k.endswith(nv) or k.startswith(nv))
                ]
                others = [
                    h
                    for h in hits
                    if normalize("culprit_name", h) != normalize("culprit_name", canon)
                ]
                if others:
                    p.append(f"R3 variant {v!r} also fits suspect {others[0]!r}: ambiguous answer")
    if "unlock_code" in kinds:
        if not codes:
            p.append("R1 unlock_code: the code is missing")
        for c in codes:
            n = normalize("unlock_code", c)
            if not re.fullmatch(r"[A-Z0-9]{3,8}", n):
                p.append(f"R2 unlock_code {c!r}: 3-8 letters/digits, no symbols")
            elif TRIVIAL_CODES.search(n):
                p.append(f"R4 unlock_code {c!r} is guessable (repeated or running digits)")
    return p


def site_problems(spec: Any, book_id: str) -> list[str]:
    """R5-R8: what the website needs to show the book, link the series and issue rewards."""
    p: list[str] = []
    pre = str(getattr(spec, "book_code_prefix", "") or "")
    if pre and not PREFIX_RE.fullmatch(pre):
        p.append(f"R6 book_code_prefix {pre!r}: 4-8 capitals/digits, starting with a letter")
    sid = getattr(spec, "series_id", "")
    order, total = (
        int(getattr(spec, "series_order", 0) or 0),
        int(getattr(spec, "series_total", 0) or 0),
    )
    if sid:
        if not (1 <= order <= max(total, 1)):
            p.append(f"R7 series_order {order} must be 1..series_total ({total})")
        if not 8 <= total <= 12:
            p.append(f"R7 series_total {total}: a series has 8-12 books")
        if order < total and not getattr(spec, "next_book_id", ""):
            p.append("R7 next_book_id is missing (needed for the 15% next-book coupon)")
        if order == total and getattr(spec, "next_book_id", ""):
            p.append(
                "R7 the last book of a series has no next_book_id (the reward is the series gift)"
            )
    ending = str(getattr(spec, "extended_ending", "") or "")
    words = len(ending.split())
    if ending and not 80 <= words <= 450:
        p.append(f"R8 extended_ending has {words} words (keep 80-450)")
    if book_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}", book_id):
        p.append(f"R5 book_id {book_id!r} is not URL-safe for the QR link")
    return p
