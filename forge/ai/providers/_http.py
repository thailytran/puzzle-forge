from __future__ import annotations

from typing import Any

import httpx

from forge.ai.base import ProviderError

TIMEOUT = httpx.Timeout(600.0, connect=15.0)


def post_json(
    client: httpx.Client, url: str, body: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    try:
        r = client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise ProviderError(f"{url.split('/')[2]} unreachable: {exc}") from exc
    if r.status_code >= 400:
        raise ProviderError(f"{url.split('/')[2]} HTTP {r.status_code}: {r.text[:200]}")
    return dict(r.json())


def get_json(client: httpx.Client, url: str, headers: dict[str, str]) -> dict[str, Any]:
    try:
        r = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ProviderError(f"{url.split('/')[2]} unreachable: {exc}") from exc
    if r.status_code >= 400:
        raise ProviderError(f"{url.split('/')[2]} HTTP {r.status_code}: {r.text[:200]}")
    return dict(r.json())
