"""External services behind small interfaces (tests use fakes; real ones use httpx).

Etsy Open API v3, Shopify Admin GraphQL, Klaviyo, Telegram, Cloudflare Turnstile.
Endpoint shapes checked 2026-11-07; re-check versions when going live (docs/CASEVAULT.md).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

from casevault.config import Settings

Lookup = Literal["found", "not_found", "unavailable"]
TIMEOUT = 20.0


class ProviderError(Exception):
    pass


@dataclass
class OrderLookup:
    status: Lookup
    lines: list[dict[str, str]] = field(default_factory=list)  # listing_id/product_id, title, sku
    detail: str = ""


class EtsyOrders(Protocol):
    def lookup(self, order_id: str) -> OrderLookup: ...


class ShopifyApi(Protocol):
    def find_order(self, name: str) -> OrderLookup: ...

    def create_discount(
        self, code: str, percent: int, ends_at: datetime, product_id: str | None, title: str
    ) -> str: ...


class Klaviyo(Protocol):
    def upsert_profile(self, email: str, attrs: dict[str, Any]) -> None: ...

    def subscribe(self, email: str, consented_at: datetime, source: str) -> None: ...

    def unsubscribe(self, email: str) -> None: ...

    def event(self, name: str, email: str, props: dict[str, Any], unique_id: str) -> None: ...


class Telegram(Protocol):
    def send(self, text: str) -> None: ...


class Captcha(Protocol):
    def verify(self, token: str, ip: str) -> bool: ...


def _client(transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, transport=transport)


# --------------------------------------------------------------------------- Etsy
class EtsyApi:
    """GET /v3/application/shops/{shop_id}/receipts/{receipt_id} (scope transactions_r).

    OAuth tokens (access 1 h, refresh 90 days) live in ETSY_TOKEN_FILE on the server."""

    BASE = "https://api.etsy.com/v3"

    def __init__(self, s: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s, self.http = s, _client(transport)

    def _token(self) -> str | None:
        p = Path(self.s.etsy_token_file)
        if not p.exists():
            return None
        tok = json.loads(p.read_text())
        if tok.get("expires_at", 0) - 60 < time.time():
            r = self.http.post(
                f"{self.BASE}/public/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.s.etsy_api_key.split(":")[0],
                    "refresh_token": tok["refresh_token"],
                },
            )
            r.raise_for_status()
            new = r.json()
            tok = {
                "access_token": new["access_token"],
                "refresh_token": new.get("refresh_token", tok["refresh_token"]),
                "expires_at": time.time() + int(new.get("expires_in", 3600)),
            }
            p.write_text(json.dumps(tok))
        return str(tok["access_token"])

    def lookup(self, order_id: str) -> OrderLookup:
        if not (self.s.etsy_api_key and self.s.etsy_shop_id):
            return OrderLookup("unavailable", detail="Etsy API not configured")
        try:
            token = self._token()
            if not token:
                return OrderLookup("unavailable", detail="no Etsy OAuth token yet")
            r = self.http.get(
                f"{self.BASE}/application/shops/{self.s.etsy_shop_id}/receipts/{order_id}",
                headers={"x-api-key": self.s.etsy_api_key, "Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            return OrderLookup("unavailable", detail=str(exc))
        if r.status_code == 404:
            return OrderLookup("not_found")
        if r.status_code >= 400:
            return OrderLookup("unavailable", detail=f"HTTP {r.status_code}")
        data = r.json()
        lines = [
            {
                "listing_id": str(t.get("listing_id", "")),
                "title": str(t.get("title", "")),
                "sku": str(t.get("sku") or ""),
            }
            for t in data.get("transactions", [])
        ]
        return OrderLookup("found", lines)


# --------------------------------------------------------------------------- Shopify
_ORDER_Q = """query($q: String!) { orders(first: 1, query: $q) { nodes { id name
  lineItems(first: 100) { nodes { title sku product { id } } } } } }"""

_DISCOUNT_M = """mutation($d: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $d) {
  codeDiscountNode { id } userErrors { field message } } }"""


class ShopifyAdmin:
    """Admin GraphQL. Scopes: read_orders (last 60 days; read_all_orders for older),
    write_discounts."""

    def __init__(self, s: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s, self.http = s, _client(transport)

    @property
    def configured(self) -> bool:
        return bool(self.s.shopify_shop and self.s.shopify_token)

    def _gql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        url = f"https://{self.s.shopify_shop}/admin/api/{self.s.shopify_api_version}/graphql.json"
        r = self.http.post(
            url,
            json={"query": query, "variables": variables},
            headers={"X-Shopify-Access-Token": self.s.shopify_token},
        )
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise ProviderError(str(body["errors"])[:300])
        return dict(body["data"])

    def find_order(self, name: str) -> OrderLookup:
        if not self.configured:
            return OrderLookup("unavailable", detail="Shopify not configured")
        q = name if name.startswith("#") else f"#{name}"
        try:
            nodes = self._gql(_ORDER_Q, {"q": f"name:{q}"})["orders"]["nodes"]
        except (httpx.HTTPError, ProviderError) as exc:
            return OrderLookup("unavailable", detail=str(exc))
        if not nodes:
            return OrderLookup("not_found")
        lines = [
            {
                "product_id": str((li.get("product") or {}).get("id", "")),
                "title": str(li.get("title", "")),
                "sku": str(li.get("sku") or ""),
            }
            for li in nodes[0]["lineItems"]["nodes"]
        ]
        return OrderLookup("found", lines)

    def create_discount(
        self, code: str, percent: int, ends_at: datetime, product_id: str | None, title: str
    ) -> str:
        if not self.configured:
            raise ProviderError("Shopify not configured")
        items: dict[str, Any] = (
            {"products": {"productsToAdd": [product_id]}} if product_id else {"all": True}
        )
        d = {
            "title": title,
            "code": code,
            "startsAt": datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            "endsAt": ends_at.isoformat() + "Z",
            "usageLimit": 1,
            "appliesOncePerCustomer": True,
            "context": {"all": "ALL"},
            "customerGets": {"value": {"percentage": percent / 100}, "items": items},
            "combinesWith": {
                "orderDiscounts": False,
                "productDiscounts": False,
                "shippingDiscounts": False,
            },
        }
        try:
            res = self._gql(_DISCOUNT_M, {"d": d})["discountCodeBasicCreate"]
        except httpx.HTTPError as exc:
            raise ProviderError(str(exc)) from exc
        if res.get("userErrors"):
            raise ProviderError(str(res["userErrors"])[:300])
        return code


# --------------------------------------------------------------------------- Klaviyo
class KlaviyoApi:
    BASE = "https://a.klaviyo.com/api"
    REVISION = "2025-10-15"

    def __init__(self, s: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s, self.http = s, _client(transport)

    def _post(self, path: str, body: dict[str, Any]) -> None:
        if not self.s.klaviyo_api_key:
            raise ProviderError("Klaviyo not configured")
        r = self.http.post(
            f"{self.BASE}{path}",
            json=body,
            headers={
                "Authorization": f"Klaviyo-API-Key {self.s.klaviyo_api_key}",
                "revision": self.REVISION,
                "accept": "application/vnd.api+json",
                "content-type": "application/vnd.api+json",
            },
        )
        if r.status_code >= 400:
            raise ProviderError(f"Klaviyo {path}: HTTP {r.status_code} {r.text[:200]}")

    def upsert_profile(self, email: str, attrs: dict[str, Any]) -> None:
        a = dict(attrs)
        top = {k: a.pop(k) for k in ("first_name",) if k in a}
        country = a.get("country")
        body = {
            "data": {
                "type": "profile",
                "attributes": {
                    "email": email,
                    **top,
                    **({"location": {"country": country}} if country else {}),
                    "properties": a,
                },
            }
        }
        self._post("/profile-import", body)

    def _sub_job(self, kind: str, profile: dict[str, Any], extra: dict[str, Any]) -> None:
        body = {
            "data": {
                "type": f"profile-subscription-bulk-{kind}-job",
                "attributes": {"profiles": {"data": [{"type": "profile", "attributes": profile}]}}
                | extra,
                "relationships": {"list": {"data": {"type": "list", "id": self.s.klaviyo_list_id}}},
            }
        }
        self._post(f"/profile-subscription-bulk-{kind}-jobs", body)

    def subscribe(self, email: str, consented_at: datetime, source: str) -> None:
        profile = {
            "email": email,
            "subscriptions": {
                "email": {
                    "marketing": {"consent": "SUBSCRIBED", "consented_at": consented_at.isoformat()}
                }
            },
        }
        self._sub_job("create", profile, {"custom_source": source})

    def unsubscribe(self, email: str) -> None:
        self._sub_job("delete", {"email": email}, {})

    def event(self, name: str, email: str, props: dict[str, Any], unique_id: str) -> None:
        body = {
            "data": {
                "type": "event",
                "attributes": {
                    "properties": props,
                    "unique_id": unique_id,
                    "metric": {"data": {"type": "metric", "attributes": {"name": name}}},
                    "profile": {"data": {"type": "profile", "attributes": {"email": email}}},
                },
            }
        }
        self._post("/events", body)


# --------------------------------------------------------------------------- Telegram / captcha
class TelegramBot:
    def __init__(self, s: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s, self.http = s, _client(transport)

    def send(self, text: str) -> None:
        if not (self.s.telegram_bot_token and self.s.telegram_chat_id):
            return  # optional
        r = self.http.post(
            f"https://api.telegram.org/bot{self.s.telegram_bot_token}/sendMessage",
            json={"chat_id": self.s.telegram_chat_id, "text": text[:4000]},
        )
        if r.status_code >= 400:
            raise ProviderError(f"Telegram HTTP {r.status_code}")


class Turnstile:
    URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def __init__(self, s: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s, self.http = s, _client(transport)

    def verify(self, token: str, ip: str) -> bool:
        if not self.s.turnstile_secret:
            return True  # dev only; /healthz reports it as missing
        try:
            r = self.http.post(
                self.URL,
                data={"secret": self.s.turnstile_secret, "response": token, "remoteip": ip},
            )
            return bool(r.json().get("success"))
        except (httpx.HTTPError, ValueError):
            return False


@dataclass
class Providers:
    etsy: EtsyOrders
    shopify: ShopifyApi
    klaviyo: Klaviyo
    telegram: Telegram
    captcha: Captcha

    @classmethod
    def real(cls, s: Settings) -> Providers:
        return cls(EtsyApi(s), ShopifyAdmin(s), KlaviyoApi(s), TelegramBot(s), Turnstile(s))


def new_unique_id() -> str:
    return uuid.uuid4().hex
