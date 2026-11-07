"""L1 — per-puzzle checks (docs/QA_SPEC.md §3)."""

from __future__ import annotations

from typing import Any

from forge.core.models import LEVELS, Puzzle
from forge.core.registry import Registry
from forge.puzzles.registry import get_puzzle_type
from forge.qa.checks import Finding, Skip, check
from forge.qa.solvers2 import SOLVERS, matches_stored
from forge.wordlists import blocklist, normalize_word

KIDS = ("kids_6_8", "kids_9_12")


def band_ok(declared: str, measured: str, audience: str) -> bool:
    """Adults: exact band. Kids: exact or one band lower (gentler is fine)."""
    d, m = LEVELS.index(declared), LEVELS.index(measured)  # type: ignore[arg-type]
    return m == d or (audience in KIDS and m == d - 1)


def _ev(n: int, p: Puzzle, **kw: Any) -> dict[str, Any]:
    return {"puzzle_n": n, "puzzle_id": p.id, "type": p.type, **kw}


def _each(ctx: Any) -> list[tuple[int, Puzzle]]:
    return list(enumerate(ctx.puzzles, 1))


@check(
    "L1.dual_solver",
    "BLOCKER",
    "Second solver (different algorithm) reproduces the stored solution",
)
def dual_solver(ctx: Any) -> list[Finding]:
    out = []
    for n, p in _each(ctx):
        solver = SOLVERS.get(p.type)
        if solver is None:
            out.append(Finding(message=f"#{n}: no second solver for {p.type}", evidence=_ev(n, p)))
            continue
        count, sol = solver(p)
        if count != 1 or not matches_stored(p, sol):
            out.append(
                Finding(
                    message=f"#{n}: second solver found {count} solution(s) / mismatch",
                    evidence=_ev(n, p, solutions=count),
                )
            )
    return out


@check("L1.unique", "BLOCKER", "Exactly one solution (type solver)")
def unique(ctx: Any) -> list[Finding]:
    out = []
    for n, p in _each(ctx):
        rep = get_puzzle_type(p.type).verify(p)
        if rep.unique is False:
            out.append(Finding(message=f"#{n}: not unique", evidence=_ev(n, p)))
    return out


@check("L1.rules", "BLOCKER", "Type rules hold (independent verify)")
def rules(ctx: Any) -> list[Finding]:
    out = []
    for n, p in _each(ctx):
        rep = get_puzzle_type(p.type).verify(p)
        if not rep.ok:
            out.append(
                Finding(
                    message=f"#{n}: {'; '.join(rep.messages)[:200]}",
                    evidence=_ev(n, p, messages=rep.messages),
                )
            )
        if p.type == "crossword" and p.data.get("mode") == "clues":
            for word, clue in p.data.get("clues", {}).items():
                if word[:4].lower() in normalize_word(clue).lower():
                    out.append(
                        Finding(
                            message=f"#{n}: clue for {word} contains the answer/stem",
                            evidence=_ev(n, p, word=word, clue=clue),
                        )
                    )
    return out


@check("L1.difficulty_band", "MAJOR", "Measured difficulty within the declared level")
def difficulty_band(ctx: Any) -> list[Finding]:
    out = []
    for n, p in _each(ctx):
        measured = get_puzzle_type(p.type).difficulty(p)
        if not band_ok(p.spec.level, measured.label, p.spec.audience):
            out.append(
                Finding(
                    message=f"#{n}: declared {p.spec.level}, "
                    f"measured {measured.label} ({measured.score})",
                    evidence=_ev(
                        n, p, declared=p.spec.level, measured=measured.label, score=measured.score
                    ),
                )
            )
    return out


def _texts(p: Puzzle) -> list[str]:
    d, s = p.data, p.solution
    if p.type == "wordsearch":
        return list(d["words"])
    if p.type == "scramble":
        return list(s["answers"]) + ([s["bonus"]] if s.get("bonus") else [])
    if p.type == "crossword":
        return list(d["words"]) + list(d.get("clues", {}).values())
    if p.type == "cryptogram":
        return [s["plain"]]
    return []


@check("L1.kid_safety", "BLOCKER", "Kids' books: no blocklisted word in any puzzle text")
def kid_safety(ctx: Any) -> list[Finding]:
    if ctx.manifest["spec"]["book"]["audience"] not in KIDS:
        raise Skip("not a kids' book")
    bad = blocklist()
    out = []
    for n, p in _each(ctx):
        for text in _texts(p):
            hits = sorted({w for w in (normalize_word(x) for x in text.split()) if w in bad})
            if hits:
                out.append(
                    Finding(message=f"#{n}: blocked words {hits}", evidence=_ev(n, p, words=hits))
                )
    return out


@check("L1.catalog_unique", "BLOCKER", "content_hash unique across the whole catalog")
def catalog_unique(ctx: Any) -> list[Finding]:
    out = []
    seen: dict[str, int] = {}
    with Registry(ctx.db_path) as reg:
        for n, p in _each(ctx):
            if p.content_hash in seen:
                out.append(
                    Finding(
                        message=f"#{n} duplicates #{seen[p.content_hash]} in this book",
                        evidence=_ev(n, p),
                    )
                )
            seen[p.content_hash] = n
            owner = reg.owner(p.content_hash)
            if owner not in (None, ctx.book_id):
                out.append(
                    Finding(
                        message=f"#{n} already used in book {owner}",
                        evidence=_ev(n, p, other_book=owner),
                    )
                )
            if owner is None:
                out.append(Finding(message=f"#{n} missing from the registry", evidence=_ev(n, p)))
    return out
