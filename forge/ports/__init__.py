"""Ports (interfaces) between the Puzzle Forge core and the outside world.

The core (`forge/core`, `forge/puzzles`, `forge/book`, `forge/qa`, `forge/mystery`) depends only on
these protocols. Adapters in `forge/adapters/` implement them: standalone today (SQLite, files,
console), HALOSPARK SUITE later (shared DB, Product Hub, Research, Listing). See
docs/INTEGRATION_HALOSPARK.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from forge.core.models import Puzzle

# ------------------------------------------------------------------ storage


@runtime_checkable
class PuzzleRegistryPort(Protocol):
    """Catalog-wide puzzle dedupe (today: forge.core.registry.Registry on SQLite)."""

    def owner(self, content_hash: str) -> str | None: ...

    def add(self, puzzle: Puzzle, book_id: str) -> None: ...

    def remove_book(self, book_id: str) -> int: ...


@runtime_checkable
class BookStatePort(Protocol):
    """Book state machine with history (today: forge.qa.state.StateStore on SQLite)."""

    def current(self, book_id: str) -> str | None: ...

    def transition(self, book_id: str, to: str, actor: str = ..., note: str = ...) -> None: ...


# ------------------------------------------------------------------ SKU


@dataclass(frozen=True)
class SkuRequest:
    book_id: str
    title: str
    audience_code: str  # Portal code, e.g. KID4 / ADULT
    brand: str
    line: str
    format: str
    series_code: str | None = None
    volume_no: int | None = None
    keyword_main: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkuResult:
    sku: str
    provider: str
    raw: dict[str, Any] = field(default_factory=dict)


class SkuError(RuntimeError):
    pass


@runtime_checkable
class SkuPort(Protocol):
    name: str

    def assign(self, req: SkuRequest) -> SkuResult: ...


# ------------------------------------------------------------------ research / listing / notify


@dataclass(frozen=True)
class BookIdea:
    """A brief coming from research (Halospark Research module or a local CSV)."""

    idea_id: str
    topic: str
    audience: str
    keyword_main: str = ""
    keywords: list[str] = field(default_factory=list)
    notes: str = ""


@runtime_checkable
class ResearchInputPort(Protocol):
    def ideas(self, limit: int = 20) -> list[BookIdea]: ...


@runtime_checkable
class ListingOutputPort(Protocol):
    """Hands an approved book (book_card + files) to whatever publishes listings."""

    def submit(self, sku: str, book_card: dict[str, Any], files: dict[str, str]) -> str: ...


@runtime_checkable
class NotificationPort(Protocol):
    def notify(self, event: str, message: str, data: dict[str, Any] | None = None) -> None: ...
