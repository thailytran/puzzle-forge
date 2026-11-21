"""The interface every puzzle type implements (see CLAUDE.md §5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from forge.core.models import DifficultyScore, Puzzle, PuzzleSpec, SolveResult, VerifyReport


@dataclass(frozen=True)
class RenderCtx:
    """Where and how a block is rendered (sizes in inches)."""

    width_in: float
    height_in: float
    large_print: bool = False
    color: bool = False
    font_size_pt: float = 11.0


@dataclass
class RenderedBlock:
    """Page content as layout blocks (see forge/layout/document.py) + side files they use."""

    blocks: list[dict[str, Any]]
    files: dict[str, bytes] = field(default_factory=dict)


@runtime_checkable
class PuzzleType(Protocol):
    name: str

    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle: ...

    def solve(self, puzzle: Puzzle) -> SolveResult: ...

    def verify(self, puzzle: Puzzle) -> VerifyReport: ...

    def difficulty(self, puzzle: Puzzle) -> DifficultyScore: ...

    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock: ...

    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock: ...
