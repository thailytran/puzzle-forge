""" "All clues required" check (docs/MYSTERY_DESIGN.md §15, QA L4.all_clues_required).

A case declares a candidate space and declarative clues. The final answer is valid only when:
  * all clues  -> exactly one candidate, equal to the declared answer;
  * drop any single clue -> more than one candidate (every clue is necessary).

Space (dict):
  {"candidates": [{"name": "Reed", "hat": "red", ...}, ...]}             # suspects / locations
  {"code": {"length": 4, "alphabet": "0123456789"}}                      # unlock codes
Code candidates get fields d1..dn (str), "code", "sum" (digit sum) and "even_count".
Clue (dict): {"field": f, "op": eq|ne|in|not_in|lt|le|gt|ge, "value": v}
           | {"any_of": [clue, ...]} | {"all_of": [clue, ...]} | {"not": clue}
           | {"distinct": [field, ...]}
Each clue may carry "id" and "text" (shown in the report).
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

Candidate = dict[str, Any]
Clue = dict[str, Any]

MAX_CODE_SPACE = 2_000_000
OPS = ("eq", "ne", "in", "not_in", "lt", "le", "gt", "ge")


class CaseError(ValueError):
    pass


def _code_candidates(length: int, alphabet: str) -> Iterator[Candidate]:
    if len(alphabet) ** length > MAX_CODE_SPACE:
        raise CaseError(f"code space {len(alphabet)}^{length} too large")
    for combo in itertools.product(alphabet, repeat=length):
        c: Candidate = {f"d{i + 1}": ch for i, ch in enumerate(combo)}
        c["code"] = "".join(combo)
        digits = [int(ch) for ch in combo if ch.isdigit()]
        c["sum"] = sum(digits)
        c["even_count"] = sum(1 for d in digits if d % 2 == 0)
        yield c


def candidates(space: dict[str, Any]) -> list[Candidate]:
    if "candidates" in space:
        cands = [dict(c) for c in space["candidates"]]
        if not cands:
            raise CaseError("empty candidate list")
        return cands
    if "code" in space:
        spec = space["code"]
        return list(_code_candidates(int(spec["length"]), str(spec.get("alphabet", "0123456789"))))
    raise CaseError("space needs 'candidates' or 'code'")


def _cmp(op: str, a: Any, b: Any) -> bool:
    if op == "eq":
        return bool(a == b)
    if op == "ne":
        return bool(a != b)
    if op == "in":
        return a in b
    if op == "not_in":
        return a not in b
    if op == "lt":
        return bool(a < b)
    if op == "le":
        return bool(a <= b)
    if op == "gt":
        return bool(a > b)
    if op == "ge":
        return bool(a >= b)
    raise CaseError(f"unknown op {op!r}")


def holds(clue: Clue, c: Candidate) -> bool:
    if "any_of" in clue:
        return any(holds(x, c) for x in clue["any_of"])
    if "all_of" in clue:
        return all(holds(x, c) for x in clue["all_of"])
    if "not" in clue:
        return not holds(clue["not"], c)
    if "distinct" in clue:
        vals = [c[f] for f in clue["distinct"]]
        return len(set(vals)) == len(vals)
    f, op = clue.get("field"), clue.get("op")
    if f is None or op not in OPS:
        raise CaseError(f"bad clue {clue!r}")
    if f not in c:
        raise CaseError(f"clue field {f!r} not in candidates")
    return _cmp(str(op), c[f], clue.get("value"))


def survivors(cands: list[Candidate], clues: list[Clue]) -> list[Candidate]:
    return [c for c in cands if all(holds(cl, c) for cl in clues)]


def _key(c: Candidate, answer_field: str) -> Any:
    return c.get(answer_field, c.get("code"))


@dataclass
class NecessityReport:
    answer_field: str
    solutions: list[Any]
    expected: Any
    redundant: list[str] = field(default_factory=list)  # clues whose removal keeps 1 candidate
    dropped: dict[str, list[Any]] = field(default_factory=dict)  # clue id -> survivors (max 10)

    @property
    def unique(self) -> bool:
        return len(self.solutions) == 1

    @property
    def ok(self) -> bool:
        right = self.expected is None or (self.unique and self.solutions[0] == self.expected)
        return self.unique and right and not self.redundant

    def problems(self) -> list[str]:
        out = []
        if not self.unique:
            out.append(f"all clues leave {len(self.solutions)} candidates: {self.solutions[:10]}")
        elif self.expected is not None and self.solutions[0] != self.expected:
            out.append(f"clues point at {self.solutions[0]!r}, declared answer {self.expected!r}")
        out += [
            f"clue {cid} is not needed (answer still unique without it)" for cid in self.redundant
        ]
        return out


def check_case(case: dict[str, Any]) -> NecessityReport:
    """case = {"space": ..., "clues": [...], "answer": value, "answer_field": "name"}."""
    cands = candidates(case["space"])
    clues: list[Clue] = list(case["clues"])
    if not clues:
        raise CaseError("case has no clues")
    afield = str(case.get("answer_field", "name" if "candidates" in case["space"] else "code"))
    ids = [str(cl.get("id", f"c{i + 1}")) for i, cl in enumerate(clues)]
    sols = [_key(c, afield) for c in survivors(cands, clues)]
    rep = NecessityReport(afield, sols, case.get("answer"))
    for i, cid in enumerate(ids):
        rest = survivors(cands, clues[:i] + clues[i + 1 :])
        rep.dropped[cid] = [_key(c, afield) for c in rest[:10]]
        if len(rest) <= 1:
            rep.redundant.append(cid)
    return rep
