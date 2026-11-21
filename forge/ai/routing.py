"""configs/ai_routing.yaml + configs/ai_pricing.yaml (override files in the config dir win)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from forge.config import REPO_ROOT

DEFAULT_ROUTING = REPO_ROOT / "configs" / "ai_routing.yaml"
DEFAULT_PRICING = REPO_ROOT / "configs" / "ai_pricing.yaml"


@dataclass(frozen=True)
class Target:
    provider: str
    model: str


@dataclass
class Route:
    task: str
    provider: str
    model: str
    max_tokens: int
    effort: str | None
    temperature: float | None
    fallback: list[Target] = field(default_factory=list)

    def candidates(self) -> list[Target]:
        return [Target(self.provider, self.model), *self.fallback]


def _load(name: str, config_dir: Path | None, default: Path) -> dict[str, Any]:
    p = config_dir / name if config_dir else None
    src = p if p is not None and p.is_file() else default
    return dict(yaml.safe_load(src.read_text(encoding="utf-8")) or {})


class Routing:
    def __init__(self, data: dict[str, Any], pricing: dict[str, Any], env: str = "dev") -> None:
        self.data, self.pricing, self.env = data, pricing, env

    @classmethod
    def load(cls, config_dir: Path | None = None, env: str = "dev") -> Routing:
        return cls(
            _load("ai_routing.yaml", config_dir, DEFAULT_ROUTING),
            _load("ai_pricing.yaml", config_dir, DEFAULT_PRICING),
            env,
        )

    def tasks(self) -> list[str]:
        return sorted(self.data.get("tasks", {}))

    def route(self, task: str) -> Route:
        d = dict(self.data.get("defaults", {}))
        override = (self.data.get("tasks") or {}).get(task)
        if override is None:
            raise KeyError(f"AI task {task!r} is not in ai_routing.yaml")
        d.update(override)
        if "provider" in override and "fallback" not in override:
            d["fallback"] = [
                f for f in d.get("fallback", []) if f.get("provider") != override["provider"]
            ]
        return Route(
            task=task,
            provider=str(d["provider"]),
            model=str(d["model"]),
            max_tokens=int(d.get("max_tokens", 16000)),
            effort=d.get("effort"),
            temperature=d.get("temperature"),
            fallback=[Target(str(f["provider"]), str(f["model"])) for f in d.get("fallback") or []],
        )

    def price(self, provider: str, model: str) -> tuple[float, float]:
        table = self.pricing.get(provider, {})
        p = table.get(model) or table.get("default") or {"input": 0.0, "output": 0.0}
        return float(p["input"]), float(p["output"])

    def cost(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
        pin, pout = self.price(provider, model)
        return (tokens_in * pin + tokens_out * pout) / 1_000_000

    def budget(self) -> dict[str, float]:
        b = dict(self.data.get("budget", {}))
        b.update((self.data.get("budget_by_env") or {}).get(self.env, {}))
        return {k: float(v) for k, v in b.items()}

    @property
    def cache_enabled(self) -> bool:
        return bool((self.data.get("cache") or {}).get("enabled", True))

    @property
    def cache_ttl_days(self) -> int:
        return int((self.data.get("cache") or {}).get("ttl_days", 90))
