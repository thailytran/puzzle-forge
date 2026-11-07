"""Shared types for the AI gateway and its provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class AIError(Exception):
    pass


class ProviderError(AIError):
    """A provider call failed (network, HTTP error, refusal, invalid output) -> try the fallback."""


class BudgetExceeded(AIError):
    """A day / month / book budget is used up: the call is not made (no fallback)."""


@dataclass(frozen=True)
class Image:
    mime: str  # image/png | image/jpeg
    data: bytes


@dataclass
class ProviderCall:
    model: str
    prompt: str
    system: str = ""
    images: list[Image] = field(default_factory=list)
    json_schema: dict[str, Any] | None = None
    max_tokens: int = 16000
    temperature: float | None = None  # omitted when None (some models reject it)
    effort: str | None = None  # Anthropic output_config.effort
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str = ""


@dataclass
class AIResult:
    task: str
    provider: str
    model: str
    text: str
    data: Any = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    fallback_from: list[str] = field(default_factory=list)


class AIProvider(Protocol):
    name: str

    def call(self, c: ProviderCall) -> ProviderResult: ...

    def list_models(self) -> list[str]: ...
