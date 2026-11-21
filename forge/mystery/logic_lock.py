"""Logic lock for deduction cases (docs/MYSTERY_DESIGN.md §10, QA L4.case_unique / L4.hint_size).

A second solver, written independently of `necessity` (set algebra over exclusion sets instead of
candidate filtering), plus the rules that keep a case fair:

  * both solvers agree: all clues leave exactly the declared answer;
  * every clue is a *small hint*: it crosses out at least one suspect, never the culprit, never
    more than `max_share` of the suspects, and on its own leaves at least `min_left` suspects;
  * every clue has a suspect only it removes (both solvers must name the same redundant clues);
  * a wrong reading (decoy row of an evidence card) never produces a single wrong culprit:
    with any one decoy in place of the true clue the case ends with 0 or >= 2 suspects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Rule = dict[str, Any]


class LockError(ValueError):
    pass


_BIN = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
}


def _test(rule: Rule, s: dict[str, Any]) -> bool:
    if "all_of" in rule:
        return all(_test(r, s) for r in rule["all_of"])
    if "any_of" in rule:
        return any(_test(r, s) for r in rule["any_of"])
    if "not" in rule:
        return not _test(rule["not"], s)
    try:
        fn = _BIN[rule["op"]]
        return bool(fn(s[rule["field"]], rule.get("value")))
    except KeyError as e:
        raise LockError(f"bad rule {rule!r}: {e}") from e


def excluded(rule: Rule | None, suspects: list[dict[str, Any]]) -> frozenset[int]:
    """Indices of the suspects a rule crosses out (None = the row says nothing)."""
    if rule is None:
        return frozenset()
    return frozenset(i for i, s in enumerate(suspects) if not _test(rule, s))


@dataclass
class LockReport:
    problems: list[str] = field(default_factory=list)
    solutions: list[Any] = field(default_factory=list)
    redundant: list[str] = field(default_factory=list)
    removed: dict[str, int] = field(default_factory=dict)  # clue id -> suspects crossed out
    left_after: list[int] = field(default_factory=list)  # suspects left after clue 1..n in order

    @property
    def ok(self) -> bool:
        return not self.problems


def check_logic(
    suspects: list[dict[str, Any]],
    answer: Any,
    clues: list[tuple[str, Rule]],
    decoys: dict[str, list[tuple[str, Rule | None]]] | None = None,
    answer_field: str = "name",
    min_left: int = 3,
    max_share: float = 0.5,
) -> LockReport:
    rep = LockReport()
    p = rep.problems
    n = len(suspects)
    everyone = frozenset(range(n))
    who = [s.get(answer_field) for s in suspects]
    if answer not in who:
        return LockReport([f"answer {answer!r} is not a suspect"])
    culprit = who.index(answer)
    cut = {cid: excluded(rule, suspects) for cid, rule in clues}
    left = everyone
    for cid, _ in clues:
        left = left - cut[cid]
        rep.left_after.append(len(left))
    rep.solutions = [who[i] for i in sorted(left)]
    if rep.solutions != [answer]:
        p.append(f"second solver: all clues leave {rep.solutions}, expected [{answer!r}]")
    for cid, _ in clues:
        gone = cut[cid]
        rep.removed[cid] = len(gone)
        if culprit in gone:
            p.append(f"clue {cid} crosses out the culprit")
        if not gone:
            p.append(f"clue {cid} crosses out nobody")
        if n - len(gone) < min_left:
            p.append(f"clue {cid} is too strong: alone it leaves {n - len(gone)} suspects")
        if len(gone) > max_share * n:
            p.append(f"clue {cid} is not a small hint: it removes {len(gone)} of {n} suspects")
        rest = everyone
        for other, _r in clues:
            if other != cid:
                rest = rest - cut[other]
        if len(rest) <= 1:
            rep.redundant.append(cid)
            p.append(f"clue {cid} is not needed (second solver)")
    if any(k <= 1 for k in rep.left_after[:-1]):
        p.append("the culprit is already known before the last clue")
    for cid, rows in (decoys or {}).items():
        if cid not in cut:
            p.append(f"decoys given for unknown clue {cid}")
            continue
        base = everyone
        for other, _r in clues:
            if other != cid:
                base = base - cut[other]
        for label, rule in rows:
            gone = excluded(rule, suspects)
            if gone == cut[cid]:
                p.append(f"{cid}: decoy {label} says the same as the true clue")
            if len(base - gone) == 1:
                wrong = who[next(iter(base - gone))]
                p.append(
                    f"{cid}: decoy {label} would still end with one suspect ({wrong}); "
                    "a wrong reading must be a dead end"
                )
    return rep
