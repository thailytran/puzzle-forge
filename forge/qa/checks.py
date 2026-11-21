"""Check registry. A check is a function `fn(ctx) -> list[Finding]` registered with a stable id,
a severity and a layer. Any exception inside a check is a FAIL (never a silent skip)."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["BLOCKER", "MAJOR", "MINOR"]
Status = Literal["pass", "fail", "skip"]


class Finding(BaseModel):
    """One observation of a check. No findings = pass."""

    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class CheckResult(BaseModel):
    id: str
    layer: str
    level: Severity
    status: Status
    message: str = ""
    findings: list[Finding] = Field(default_factory=list)
    waived: bool = False


class Skip(Exception):
    """Raise inside a check when it does not apply (e.g. L4 on a classic book)."""


@dataclass(frozen=True)
class CheckDef:
    id: str
    level: Severity
    layer: str
    description: str
    fn: Callable[[Any], list[Finding]]


REGISTRY: dict[str, CheckDef] = {}


def check(
    id: str, level: Severity, description: str
) -> Callable[[Callable[[Any], list[Finding]]], Callable[[Any], list[Finding]]]:
    def deco(fn: Callable[[Any], list[Finding]]) -> Callable[[Any], list[Finding]]:
        if id in REGISTRY:
            raise ValueError(f"duplicate check id {id}")
        REGISTRY[id] = CheckDef(id, level, id.split(".")[0], description, fn)
        return fn

    return deco


def run_one(d: CheckDef, ctx: Any) -> CheckResult:
    try:
        findings = d.fn(ctx)
    except Skip as s:
        return CheckResult(id=d.id, layer=d.layer, level=d.level, status="skip", message=str(s))
    except Exception as exc:  # a check that cannot run is a failure
        tb = traceback.format_exception_only(type(exc), exc)[-1].strip()
        return CheckResult(
            id=d.id,
            layer=d.layer,
            level=d.level,
            status="fail",
            message=f"check could not run: {tb}",
        )
    return CheckResult(
        id=d.id,
        layer=d.layer,
        level=d.level,
        status="fail" if findings else "pass",
        message=findings[0].message if findings else "",
        findings=findings,
    )


def run_checks(ctx: Any, layers: set[str] | None = None) -> list[CheckResult]:
    return [run_one(d, ctx) for d in REGISTRY.values() if layers is None or d.layer in layers]
