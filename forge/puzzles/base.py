"""Shared helpers for puzzle types."""

from __future__ import annotations

from forge.core.models import PuzzleSpec


class GenerationError(RuntimeError):
    """A generator could not build a valid puzzle for the spec (after all retries)."""


def find_constraint[C](spec: PuzzleSpec, kind: type[C]) -> C | None:
    for c in spec.constraints:
        if isinstance(c, kind):
            return c
    return None


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))
