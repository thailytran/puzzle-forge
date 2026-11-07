"""P10.3: AI gateway routing, fallback, JSON repair, cache, budgets, cost ledger, adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from forge.ai.base import BudgetExceeded, Image, ProviderCall, ProviderError, ProviderResult
from forge.ai.gateway import RoutedGateway, schema_errors
from forge.ai.ledger import Ledger
from forge.ai.providers.anthropic import AnthropicAdapter
from forge.ai.providers.gemini import GeminiAdapter
from forge.ai.providers.openai import OpenAIAdapter
from forge.ai.routing import Routing

SCHEMA = {
    "type": "object",
    "required": ["words"],
    "properties": {"words": {"type": "array", "items": {"type": "string"}}},
}


@dataclass
class Fake:
    name: str
    replies: list[Any] = field(default_factory=list)
    calls: list[ProviderCall] = field(default_factory=list)

    def call(self, c: ProviderCall) -> ProviderResult:
        self.calls.append(c)
        r = self.replies.pop(0) if self.replies else '{"words": ["OCEAN"]}'
        if isinstance(r, Exception):
            raise r
        return ProviderResult(text=r, model=c.model, input_tokens=1000, output_tokens=500)

    def list_models(self) -> list[str]:
        return ["m1", "m2"]


def routing(**budget: float) -> Routing:
    data = {
        "defaults": {
            "provider": "anthropic",
            "model": "claude-opus-5-5",
            "max_tokens": 1000,
            "effort": "medium",
            "fallback": [{"provider": "openai", "model": "gpt-x"}],
        },
        "tasks": {
            "word_list": {"model": "claude-sonnet-5-5"},
            "playtest_reader_B": {"provider": "openai", "model": "gpt-x"},
        },
        "budget": {
            "daily_usd": 100,
            "monthly_usd": 1000,
            "per_book_usd": 50,
            "warn_ratio": 0.8,
            **budget,
        },
        "cache": {"enabled": True, "ttl_days": 30},
    }
    pricing = {
        "anthropic": {"claude-sonnet-5-5": {"input": 2.0, "output": 10.0}},
        "openai": {"default": {"input": 10.0, "output": 40.0}},
    }
    return Routing(data, pricing)


def gw(tmp_path, providers, r=None, alerts=None):
    return RoutedGateway(
        r or routing(),
        providers,
        Ledger(tmp_path / "f.db"),
        (alerts.append if alerts is not None else None),
    )


def test_routes_and_costs(tmp_path):
    a = Fake("anthropic")
    g = gw(tmp_path, {"anthropic": a})
    res = g.complete_json("word_list", "ocean words", SCHEMA, book_id="bk")
    assert res.data == {"words": ["OCEAN"]} and res.model == "claude-sonnet-5-5"
    assert a.calls[0].effort == "medium" and a.calls[0].json_schema == SCHEMA
    assert res.cost_usd == pytest.approx((1000 * 2 + 500 * 10) / 1e6)
    rep = g.ledger.report("task")
    assert rep[0]["task"] == "word_list" and rep[0]["calls"] == 1


def test_cache_hit_costs_nothing(tmp_path):
    a = Fake("anthropic")
    g = gw(tmp_path, {"anthropic": a})
    g.complete_json("word_list", "p", SCHEMA)
    again = g.complete_json("word_list", "p", SCHEMA)
    assert again.cached and len(a.calls) == 1 and again.cost_usd == 0


def test_json_repair_then_fallback(tmp_path):
    a = Fake("anthropic", ["not json", '{"words": ["A"]}'])
    g = gw(tmp_path, {"anthropic": a})
    assert g.complete_json("word_list", "p", SCHEMA).data == {"words": ["A"]}
    assert "invalid" in a.calls[1].prompt
    a2 = Fake("anthropic", [ProviderError("anthropic refusal (cyber)")])
    o = Fake("openai")
    res = gw(tmp_path / "2", {"anthropic": a2, "openai": o}).complete_json("word_list", "q", SCHEMA)
    assert res.provider == "openai" and res.fallback_from == ["anthropic/claude-sonnet-5-5"]
    assert o.calls[0].effort is None


def test_missing_key_skips_and_all_fail(tmp_path):
    o = Fake("openai", [ProviderError("down")])
    with pytest.raises(ProviderError, match="no API key"):
        gw(tmp_path, {"openai": o}).complete_json("word_list", "p", SCHEMA)


def test_reader_b_on_other_provider_without_same_fallback():
    r = routing().route("playtest_reader_B")
    assert r.provider == "openai" and all(t.provider != "openai" for t in r.fallback)


def test_budget_stop_and_warning(tmp_path):
    alerts: list[str] = []
    g = gw(tmp_path, {"anthropic": Fake("anthropic")}, routing(per_book_usd=0.05), alerts)
    with pytest.raises(BudgetExceeded):
        for i in range(20):  # each call costs $0.007; the check reserves max_tokens ($0.01)
            g.complete_json("word_list", f"p{i}", SCHEMA, book_id="bk")
    assert i == 6  # 6 calls = $0.042 (>= 80 % warned), the 7th would pass $0.05
    assert any("book:bk" in a and "84%" in a for a in alerts)
    assert any("stopped" in a for a in alerts)
    g.complete_json("word_list", "other book", SCHEMA, book_id="bk2")  # other books go on


def test_env_budget_and_routing_file_override(tmp_path):
    (tmp_path / "ai_routing.yaml").write_text(
        "defaults: {provider: gemini, model: g1}\ntasks: {x: {}}\nbudget: {daily_usd: 9}\n"
    )
    r = Routing.load(tmp_path, "prod")
    assert r.route("x").model == "g1" and r.budget()["daily_usd"] == 9
    shipped = Routing.load(None, "test")
    assert shipped.budget()["daily_usd"] <= 1
    for t in (
        "case_bible",
        "story",
        "clues",
        "word_list",
        "crossword_clues",
        "proofread",
        "playtest_reader_A",
        "playtest_reader_B",
        "vision_qa",
        "marketing_master_prompt",
    ):
        shipped.route(t)
    a, b = shipped.route("playtest_reader_A"), shipped.route("playtest_reader_B")
    assert a.provider != b.provider


def test_schema_errors():
    assert schema_errors({"words": ["a", 1]}, SCHEMA) == ["$.words[1]: expected string"]
    assert schema_errors({}, SCHEMA) == ["$.words: missing"]


def test_vision_and_image_prompt(tmp_path):
    a = Fake("anthropic", ['{"ok": true}', "a lighthouse at dusk"])
    g = gw(tmp_path, {"anthropic": a})
    img = Image("image/png", b"\x89PNG")
    r = g.vision_judge("word_list", "check", [img], {"type": "object"})
    assert r.data == {"ok": True} and a.calls[0].images == [img]
    assert g.image_prompt("word_list", "brief").text == "a lighthouse at dusk"
    assert "No text" in a.calls[1].system


# ------------------------------------------------------------------ adapters (no network)
def test_anthropic_adapter_request_shape():
    sent: dict[str, Any] = {}

    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(
            stop_reason="end_turn",
            model=kw["model"],
            content=[SimpleNamespace(type="text", text='{"a": 1}')],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )

    client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
        messages=SimpleNamespace(create=create),
    )
    ad = AnthropicAdapter("k", client=client)
    r = ad.call(
        ProviderCall(
            model="claude-opus-5-5",
            prompt="hi",
            system="s",
            images=[Image("image/png", b"x")],
            json_schema={"type": "object"},
            effort="high",
        )
    )
    assert r.text == '{"a": 1}' and r.input_tokens == 10
    assert sent["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": {"type": "object"}},
    }
    assert sent["fallbacks"] == "default" and "temperature" not in sent
    assert sent["messages"][0]["content"][0]["type"] == "image"
    sent.clear()
    ad.call(ProviderCall(model="claude-haiku-5-5", prompt="hi"))
    assert "fallbacks" not in sent

    def refuse(**kw):
        return SimpleNamespace(
            stop_reason="refusal",
            stop_details=SimpleNamespace(category="bio"),
            content=[],
            usage=SimpleNamespace(input_tokens=1, output_tokens=0),
        )

    bad = AnthropicAdapter(
        "k", client=SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=refuse)))
    )
    with pytest.raises(ProviderError, match="refusal"):
        bad.call(ProviderCall(model="claude-opus-5-5", prompt="x"))


def test_openai_and_gemini_adapters():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if "openai" in str(req.url):
            if req.url.path.endswith("/models"):
                return httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]})
            return httpx.Response(
                200,
                json={
                    "model": "gpt-x",
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 4},
                },
            )
        if req.method == "GET":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "models/g1", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/emb", "supportedGenerationMethods": ["embedContent"]},
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "{}"}]}, "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 8},
            },
        )

    t = httpx.MockTransport(handler)
    o = OpenAIAdapter("sk", t)
    r = o.call(ProviderCall(model="gpt-x", prompt="p", json_schema={"type": "object"}))
    body = json.loads(seen[0].content)
    assert body["response_format"]["type"] == "json_schema" and "temperature" not in body
    assert r.input_tokens == 3 and o.list_models() == ["a", "b"]
    g = GeminiAdapter("gk", t)
    r = g.call(ProviderCall(model="g1", prompt="p", json_schema={}, temperature=0.2))
    gb = json.loads(seen[-1].content)
    assert seen[-1].headers["x-goog-api-key"] == "gk"
    assert gb["generationConfig"]["responseMimeType"] == "application/json"
    assert r.output_tokens == 8 and g.list_models() == ["g1"]
    fail = OpenAIAdapter("sk", httpx.MockTransport(lambda r: httpx.Response(401, text="bad key")))
    with pytest.raises(ProviderError, match="401"):
        fail.call(ProviderCall(model="m", prompt="p"))


def test_cli_ai_usage_and_test(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from forge.cli import app

    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "HALOSPARK_AI_TOKEN"):
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORGE_DB_PATH", str(tmp_path / "f.db"))
    led = Ledger(tmp_path / "f.db")
    led.record("story", "anthropic", "claude-opus-5-5", "bk", 100, 50, 0.0014)
    led.close()
    r = CliRunner().invoke(app, ["ai", "usage", "--by", "provider"])
    assert r.exit_code == 0 and "anthropic" in r.stdout and "today $0.00" in r.stdout
    r = CliRunner().invoke(app, ["ai", "test"])
    assert r.exit_code == 0 and "no key" in r.stdout
    r = CliRunner().invoke(app, ["ai", "models", "openai"])
    assert r.exit_code == 1
