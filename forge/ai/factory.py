"""Build the gateway from settings (CLI / web / worker wire this; core code takes the port)."""

from __future__ import annotations

from forge.ai.base import AIProvider
from forge.ai.gateway import RoutedGateway
from forge.ai.ledger import Ledger
from forge.ai.providers import PROVIDERS, build_provider
from forge.ai.routing import Routing
from forge.config import Settings


def providers_from(settings: Settings) -> dict[str, AIProvider]:
    out: dict[str, AIProvider] = {}
    for name in PROVIDERS:
        p = build_provider(name, settings.secret)
        if p is not None:
            out[name] = p
    return out


def gateway_from(settings: Settings) -> RoutedGateway:
    from forge.notify import notifier_from

    return RoutedGateway(
        Routing.load(settings.config_dir, settings.env),
        providers_from(settings),
        Ledger(settings.db_path),
        notifier_from(settings).text,
    )


def test_providers(settings: Settings, call: bool = False) -> list[dict[str, str]]:
    """Per provider: key present? models listed? (optional) one tiny JSON call via the router."""
    rows = []
    for name in PROVIDERS:
        p = build_provider(name, settings.secret)
        if p is None:
            rows.append({"provider": name, "status": "no key", "detail": ""})
            continue
        try:
            models = p.list_models()
            rows.append({"provider": name, "status": "ok", "detail": f"{len(models)} models"})
        except Exception as exc:  # report every failure kind in the table
            rows.append({"provider": name, "status": "fail", "detail": str(exc)[:120]})
    if call:
        g = gateway_from(settings)
        try:
            r = g.complete_json(
                "test_connection",
                'Return {"ok": true}.',
                {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}},
            )
            rows.append(
                {
                    "provider": f"call:{r.provider}",
                    "status": "ok",
                    "detail": f"{r.model} ${r.cost_usd:.5f}",
                }
            )
        except Exception as exc:
            rows.append({"provider": "call", "status": "fail", "detail": str(exc)[:120]})
    return rows
