"""Google Gemini adapter (Generative Language API over HTTPS, JSON response mime type)."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from forge.ai.base import ProviderCall, ProviderError, ProviderResult
from forge.ai.providers._http import TIMEOUT, get_json, post_json

BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiAdapter:
    name = "gemini"

    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.headers = {"x-goog-api-key": api_key}
        self.http = httpx.Client(timeout=TIMEOUT, transport=transport)

    def call(self, c: ProviderCall) -> ProviderResult:
        parts: list[dict[str, Any]] = [{"text": c.prompt}]
        parts += [
            {"inline_data": {"mime_type": i.mime, "data": base64.b64encode(i.data).decode()}}
            for i in c.images
        ]
        gen: dict[str, Any] = {"maxOutputTokens": c.max_tokens}
        if c.temperature is not None:
            gen["temperature"] = c.temperature
        if c.json_schema is not None:
            gen["responseMimeType"] = "application/json"
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": gen,
        }
        if c.system:
            body["systemInstruction"] = {"parts": [{"text": c.system}]}
        model = c.model.removeprefix("models/")
        data = post_json(self.http, f"{BASE}/models/{model}:generateContent", body, self.headers)
        try:
            cand = data["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        except (KeyError, IndexError) as exc:
            reason = data.get("promptFeedback", {}).get("blockReason", "")
            raise ProviderError(f"gemini: no candidate {reason}".strip()) from exc
        usage = data.get("usageMetadata", {})
        return ProviderResult(
            text=text,
            model=model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
            stop_reason=str(cand.get("finishReason", "")),
        )

    def list_models(self) -> list[str]:
        data = get_json(self.http, f"{BASE}/models?pageSize=200", self.headers)
        return sorted(
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )
