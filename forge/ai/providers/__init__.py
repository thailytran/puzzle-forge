"""Provider adapters. Model names never live here: they come from configs/ai_routing.yaml."""

from __future__ import annotations

from collections.abc import Callable

from forge.ai.base import AIProvider


def build_provider(name: str, secret: Callable[[str], str]) -> AIProvider | None:
    """Adapter for `name`, or None when its key is missing."""
    if name == "anthropic":
        key = secret("ANTHROPIC_API_KEY")
        if key:
            from forge.ai.providers.anthropic import AnthropicAdapter

            return AnthropicAdapter(key)
    elif name == "openai":
        key = secret("OPENAI_API_KEY")
        if key:
            from forge.ai.providers.openai import OpenAIAdapter

            return OpenAIAdapter(key)
    elif name == "gemini":
        key = secret("GEMINI_API_KEY")
        if key:
            from forge.ai.providers.gemini import GeminiAdapter

            return GeminiAdapter(key)
    elif name == "halospark":
        key = secret("HALOSPARK_AI_TOKEN")
        import os

        url = os.environ.get("HALOSPARK_AI_URL", "")
        if key and url:
            from forge.ai.providers.halospark import HalosparkAIGatewayAdapter

            return HalosparkAIGatewayAdapter(url, key)
    else:
        raise ValueError(f"unknown AI provider {name!r}")
    return None


PROVIDERS = ("anthropic", "openai", "gemini", "halospark")
