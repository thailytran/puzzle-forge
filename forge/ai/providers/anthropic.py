"""Anthropic adapter (official `anthropic` SDK, MIT).

Structured JSON uses `output_config.format` (json_schema); depth uses `output_config.effort`.
Sampling parameters are not sent (current Claude models reject temperature). Refusals: the
server-side fallback (`fallbacks: "default"`, beta header) re-runs a declined request on another
Claude model; a final refusal raises ProviderError so the gateway moves to its own fallback."""

from __future__ import annotations

import base64
from typing import Any

from forge.ai.base import ProviderCall, ProviderError, ProviderResult

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicAdapter:
    name = "anthropic"

    def __init__(self, api_key: str, client: Any = None, server_fallback: bool = True) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, max_retries=2)
        self.client = client
        self.server_fallback = server_fallback

    def call(self, c: ProviderCall) -> ProviderResult:
        import anthropic

        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.mime,
                    "data": base64.standard_b64encode(img.data).decode(),
                },
            }
            for img in c.images
        ]
        content.append({"type": "text", "text": c.prompt})
        output_config: dict[str, Any] = {}
        if c.effort:
            output_config["effort"] = c.effort
        if c.json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": c.json_schema}
        kwargs: dict[str, Any] = {
            "model": c.model,
            "max_tokens": c.max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if c.system:
            kwargs["system"] = c.system
        if output_config:
            kwargs["output_config"] = output_config
        try:
            # Haiku has no server-side refusal fallback; the gateway's own fallback still applies
            use_fb = self.server_fallback and "haiku" not in c.model
            if use_fb and c.options.get("server_fallback", True):
                msg = self.client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **kwargs
                )
            else:
                msg = self.client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"anthropic HTTP {exc.status_code}: {exc.message}"[:300]) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"anthropic unreachable: {exc}") from exc
        if msg.stop_reason == "refusal":
            cat = getattr(getattr(msg, "stop_details", None), "category", None)
            raise ProviderError(f"anthropic refusal ({cat})")
        if msg.stop_reason == "max_tokens":
            raise ProviderError("anthropic output hit max_tokens (raise max_tokens in routing)")
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return ProviderResult(
            text=text,
            model=str(getattr(msg, "model", c.model)),
            input_tokens=int(msg.usage.input_tokens),
            output_tokens=int(msg.usage.output_tokens),
            stop_reason=str(msg.stop_reason),
        )

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self.client.models.list())
