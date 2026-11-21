"""OpenAI adapter (Chat Completions over HTTPS, json_schema response format)."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from forge.ai.base import ProviderCall, ProviderError, ProviderResult
from forge.ai.providers._http import TIMEOUT, get_json, post_json

BASE = "https://api.openai.com/v1"


class OpenAIAdapter:
    name = "openai"

    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.http = httpx.Client(timeout=TIMEOUT, transport=transport)

    def call(self, c: ProviderCall) -> ProviderResult:
        parts: list[dict[str, Any]] = [{"type": "text", "text": c.prompt}]
        for img in c.images:
            url = f"data:{img.mime};base64,{base64.b64encode(img.data).decode()}"
            parts.append({"type": "image_url", "image_url": {"url": url}})
        messages: list[dict[str, Any]] = []
        if c.system:
            messages.append({"role": "system", "content": c.system})
        messages.append({"role": "user", "content": parts})
        body: dict[str, Any] = {
            "model": c.model,
            "messages": messages,
            "max_completion_tokens": c.max_tokens,
        }
        if c.temperature is not None:
            body["temperature"] = c.temperature
        if c.json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": c.json_schema, "strict": False},
            }
        data = post_json(self.http, f"{BASE}/chat/completions", body, self.headers)
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
            if choice["message"].get("refusal"):
                raise ProviderError(f"openai refusal: {choice['message']['refusal'][:100]}")
            usage = data.get("usage", {})
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"openai: unexpected response {str(data)[:200]}") from exc
        return ProviderResult(
            text=text,
            model=str(data.get("model", c.model)),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            stop_reason=str(choice.get("finish_reason", "")),
        )

    def list_models(self) -> list[str]:
        return sorted(m["id"] for m in get_json(self.http, f"{BASE}/models", self.headers)["data"])
