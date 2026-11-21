"""The AIGateway port and its routed implementation.

complete_json(task, prompt, schema)  -> validated JSON (AI writes words/clues/story, never answers)
vision_judge(task, prompt, images, schema) -> JSON judgement about rendered pages / art
image_prompt(task, brief)            -> plain-text prompt for the image tool

RoutedGateway: route from ai_routing.yaml -> cache -> budget check -> provider -> JSON check
(one repair retry) -> fallback provider on failure -> cost ledger -> 80 % budget alert."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from forge.ai.base import (
    AIProvider,
    AIResult,
    BudgetExceeded,
    Image,
    ProviderCall,
    ProviderError,
)
from forge.ai.ledger import Ledger
from forge.ai.routing import Route, Routing, Target

Notifier = Callable[[str], None]


class AIGateway(Protocol):
    def complete_json(
        self,
        task: str,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str = "",
        book_id: str = "",
        images: Sequence[Image] = (),
    ) -> AIResult: ...

    def vision_judge(
        self,
        task: str,
        prompt: str,
        images: Sequence[Image],
        schema: dict[str, Any],
        *,
        book_id: str = "",
    ) -> AIResult: ...

    def image_prompt(self, task: str, brief: str, *, book_id: str = "") -> AIResult: ...


_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def schema_errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Small JSON-schema subset: type, required, properties, items, enum."""
    errs: list[str] = []
    t = schema.get("type")
    if isinstance(t, str) and t in _TYPES:
        ok = isinstance(value, _TYPES[t]) and not (
            t in ("integer", "number") and isinstance(value, bool)
        )
        if not ok:
            return [f"{path}: expected {t}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: not one of {schema['enum']}")
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}.{k}: missing")
        for k, sub in (schema.get("properties") or {}).items():
            if k in value:
                errs += schema_errors(value[k], sub, f"{path}.{k}")
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(value):
            errs += schema_errors(item, schema["items"], f"{path}[{i}]")
    return errs


def parse_json(text: str) -> Any:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t = m.group(1)
    return json.loads(t)


class RoutedGateway:
    def __init__(
        self,
        routing: Routing,
        providers: dict[str, AIProvider],
        ledger: Ledger,
        notify: Notifier | None = None,
    ) -> None:
        self.routing, self.providers, self.ledger = routing, providers, ledger
        self.notify = notify or (lambda msg: None)

    # ---------------------------------------------------------------- public port
    def complete_json(
        self,
        task: str,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str = "",
        book_id: str = "",
        images: Sequence[Image] = (),
    ) -> AIResult:
        return self._run(task, prompt, system, list(images), schema, book_id)

    def vision_judge(
        self,
        task: str,
        prompt: str,
        images: Sequence[Image],
        schema: dict[str, Any],
        *,
        book_id: str = "",
    ) -> AIResult:
        if not images:
            raise ValueError("vision_judge needs at least one image")
        return self._run(task, prompt, "", list(images), schema, book_id)

    def image_prompt(self, task: str, brief: str, *, book_id: str = "") -> AIResult:
        system = (
            "Write one prompt for an image model. No text, letters or numbers in the "
            "image. Return only the prompt."
        )
        return self._run(task, brief, system, [], None, book_id)

    # ---------------------------------------------------------------- internals
    def _key(
        self,
        t: Target,
        route: Route,
        prompt: str,
        system: str,
        images: list[Image],
        schema: dict[str, Any] | None,
    ) -> str:
        h = hashlib.sha256()
        for part in (
            route.task,
            t.provider,
            t.model,
            system,
            prompt,
            json.dumps(schema, sort_keys=True),
            str(route.effort),
        ):
            h.update(part.encode() + b"\0")
        for img in images:
            h.update(hashlib.sha256(img.data).digest())
        return h.hexdigest()

    def _check_budget(self, estimate: float, book_id: str) -> None:
        b = self.routing.budget()
        p = self.ledger.periods()
        limits = [
            ("day", self.ledger.spent(p["day"]), b.get("daily_usd")),
            ("month", self.ledger.spent(p["month"]), b.get("monthly_usd")),
        ]
        if book_id:
            limits.append(
                (f"book {book_id}", self.ledger.spent(book_id=book_id), b.get("per_book_usd"))
            )
        for name, spent, limit in limits:
            if limit is not None and spent + estimate > limit:
                self.notify(
                    f"Puzzle Forge AI budget reached ({name}: ${spent:.2f} of ${limit:.2f})"
                    " - AI calls stopped"
                )
                raise BudgetExceeded(f"AI budget for {name} reached: ${spent:.2f} / ${limit:.2f}")

    def _warn(self, book_id: str) -> None:
        b = self.routing.budget()
        ratio = b.get("warn_ratio", 0.8)
        p = self.ledger.periods()
        checks = [
            (f"day:{p['day'].date()}", self.ledger.spent(p["day"]), b.get("daily_usd")),
            (f"month:{p['month'].date()}", self.ledger.spent(p["month"]), b.get("monthly_usd")),
        ]
        if book_id:
            checks.append(
                (f"book:{book_id}", self.ledger.spent(book_id=book_id), b.get("per_book_usd"))
            )
        for key, spent, limit in checks:
            if limit and spent >= ratio * limit and self.ledger.alert_once(key):
                self.notify(
                    f"Puzzle Forge AI spend {key}: ${spent:.2f} of ${limit:.2f} "
                    f"({spent / limit:.0%})"
                )

    def _run(
        self,
        task: str,
        prompt: str,
        system: str,
        images: list[Image],
        schema: dict[str, Any] | None,
        book_id: str,
    ) -> AIResult:
        route = self.routing.route(task)
        tried: list[str] = []
        errors: list[str] = []
        for t in route.candidates():
            key = self._key(t, route, prompt, system, images, schema)
            if self.routing.cache_enabled:
                hit = self.ledger.cache_get(key, self.routing.cache_ttl_days)
                if hit is not None:
                    self.ledger.record(task, t.provider, t.model, book_id, 0, 0, 0.0, cached=True)
                    return AIResult(
                        task=task,
                        provider=t.provider,
                        model=t.model,
                        text=hit["text"],
                        data=hit.get("data"),
                        cached=True,
                        fallback_from=tried,
                    )
            prov = self.providers.get(t.provider)
            if prov is None:
                tried.append(f"{t.provider}/{t.model}")
                errors.append(f"{t.provider}: no API key")
                continue
            pin, pout = self.routing.price(t.provider, t.model)
            estimate = (len(prompt + system) / 3.5 * pin + route.max_tokens * pout) / 1_000_000
            self._check_budget(estimate, book_id)
            try:
                res = self._call(prov, t, route, prompt, system, images, schema, book_id)
            except ProviderError as exc:
                tried.append(f"{t.provider}/{t.model}")
                errors.append(str(exc))
                continue
            res.fallback_from = tried
            if self.routing.cache_enabled:
                self.ledger.cache_put(
                    key, task, t.provider, t.model, {"text": res.text, "data": res.data}
                )
            self._warn(book_id)
            return res
        raise ProviderError(f"AI task {task}: every provider failed: " + " | ".join(errors))

    def _call(
        self,
        prov: AIProvider,
        t: Target,
        route: Route,
        prompt: str,
        system: str,
        images: list[Image],
        schema: dict[str, Any] | None,
        book_id: str,
    ) -> AIResult:
        call = ProviderCall(
            model=t.model,
            prompt=prompt,
            system=system,
            images=images,
            json_schema=schema,
            max_tokens=route.max_tokens,
            temperature=route.temperature,
            effort=route.effort if t.provider == "anthropic" else None,
            options={"task": route.task},
        )
        tin = tout = 0
        cost = 0.0
        for attempt in (1, 2):
            try:
                r = prov.call(call)
            except ProviderError as exc:
                self.ledger.record(
                    route.task, t.provider, t.model, book_id, 0, 0, 0.0, ok=False, error=str(exc)
                )
                raise
            c = self.routing.cost(t.provider, r.model, r.input_tokens, r.output_tokens)
            tin, tout, cost = tin + r.input_tokens, tout + r.output_tokens, cost + c
            if schema is None:
                self.ledger.record(
                    route.task, t.provider, r.model, book_id, r.input_tokens, r.output_tokens, c
                )
                return AIResult(route.task, t.provider, r.model, r.text, None, tin, tout, cost)
            try:
                data = parse_json(r.text)
                problems = schema_errors(data, schema)
            except ValueError as exc:
                problems = [f"not JSON: {exc}"]
            self.ledger.record(
                route.task,
                t.provider,
                r.model,
                book_id,
                r.input_tokens,
                r.output_tokens,
                c,
                ok=not problems,
                error="; ".join(problems),
            )
            if not problems:
                return AIResult(route.task, t.provider, r.model, r.text, data, tin, tout, cost)
            if attempt == 1:  # one repair round on the same model
                call.prompt = (
                    f"{prompt}\n\nYour previous answer was invalid: "
                    f"{'; '.join(problems[:5])}. Return only valid JSON for the schema."
                )
        raise ProviderError(f"{t.provider}/{t.model}: invalid JSON twice")
