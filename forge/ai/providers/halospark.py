"""Future adapter: the shared AI gateway of HALOSPARK SUITE (INTEGRATION_HALOSPARK.md §8).

Contract (proposed, to be implemented on the Suite side):
  POST {HALOSPARK_AI_URL}/v1/complete   Authorization: Bearer <HALOSPARK_AI_TOKEN>
  body {app: "puzzle-forge", task, model, system, prompt, images: [{mime, b64}], json_schema,
        max_tokens, temperature?, effort?}
  -> {text, model, provider, input_tokens, output_tokens, cost_usd}
  GET {HALOSPARK_AI_URL}/v1/models -> {models: [..]}
The Suite then owns keys, routing, budgets and cost reports for every module."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from forge.ai.base import ProviderCall, ProviderResult
from forge.ai.providers._http import TIMEOUT, get_json, post_json


class HalosparkAIGatewayAdapter:
    name = "halospark"

    def __init__(
        self, base_url: str, token: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.base = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.http = httpx.Client(timeout=TIMEOUT, transport=transport)

    def call(self, c: ProviderCall) -> ProviderResult:
        body: dict[str, Any] = {
            "app": "puzzle-forge",
            "task": c.options.get("task", ""),
            "model": c.model,
            "system": c.system,
            "prompt": c.prompt,
            "images": [
                {"mime": i.mime, "b64": base64.b64encode(i.data).decode()} for i in c.images
            ],
            "json_schema": c.json_schema,
            "max_tokens": c.max_tokens,
            "temperature": c.temperature,
            "effort": c.effort,
        }
        d = post_json(self.http, f"{self.base}/v1/complete", body, self.headers)
        return ProviderResult(
            text=str(d.get("text", "")),
            model=str(d.get("model", c.model)),
            input_tokens=int(d.get("input_tokens", 0)),
            output_tokens=int(d.get("output_tokens", 0)),
        )

    def list_models(self) -> list[str]:
        return sorted(get_json(self.http, f"{self.base}/v1/models", self.headers)["models"])
