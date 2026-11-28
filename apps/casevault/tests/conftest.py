"""Fakes for Etsy / Shopify / Klaviyo / Telegram / captcha + an app on a temp SQLite DB."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from casevault import db as T
from casevault.answers import answer_hash, code_hash
from casevault.config import Settings, load_rules
from casevault.providers import OrderLookup, ProviderError, Providers
from casevault.service import Vault
from casevault.web import create_app
from fastapi.testclient import TestClient

KEY = "test-answer-key"
TOKEN = "test-admin-token"


@dataclass
class FakeEtsy:
    receipts: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    available: bool = True  # False = API not configured -> CSV only

    def lookup(self, order_id: str) -> OrderLookup:
        if not self.available:
            return OrderLookup("unavailable")
        if order_id in self.receipts:
            return OrderLookup("found", self.receipts[order_id])
        return OrderLookup("not_found")


@dataclass
class FakeShopify:
    orders: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    discounts: list[dict[str, Any]] = field(default_factory=list)
    fail: bool = False

    def find_order(self, name: str) -> OrderLookup:
        n = name.lstrip("#")
        return (
            OrderLookup("found", self.orders[n]) if n in self.orders else OrderLookup("not_found")
        )

    def create_discount(
        self, code: str, percent: int, ends_at: datetime, product_id: str | None, title: str
    ) -> str:
        if self.fail:
            raise ProviderError("shopify down")
        self.discounts.append(
            {"code": code, "percent": percent, "ends_at": ends_at, "product_id": product_id}
        )
        return code


@dataclass
class FakeKlaviyo:
    events: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    subscribed: set[str] = field(default_factory=set)
    fail: bool = False

    def _check(self) -> None:
        if self.fail:
            raise ProviderError("klaviyo down")

    def upsert_profile(self, email: str, attrs: dict[str, Any]) -> None:
        self._check()
        self.profiles[email] = attrs

    def subscribe(self, email: str, consented_at: datetime, source: str) -> None:
        self._check()
        self.subscribed.add(email)

    def unsubscribe(self, email: str) -> None:
        self._check()
        self.subscribed.discard(email)

    def event(self, name: str, email: str, props: dict[str, Any], unique_id: str) -> None:
        self._check()
        self.events.append((name, email, props))

    def named(self, name: str, email: str | None = None) -> list[dict[str, Any]]:
        return [p for n, e, p in self.events if n == name and (email is None or e == email)]


@dataclass
class FakeTelegram:
    messages: list[str] = field(default_factory=list)

    def send(self, text: str) -> None:
        self.messages.append(text)


class FakeCaptcha:
    def verify(self, token: str, ip: str) -> bool:
        return token != "bad"


@dataclass
class Env:
    client: TestClient
    vault: Vault
    etsy: FakeEtsy
    shopify: FakeShopify
    klaviyo: FakeKlaviyo
    telegram: FakeTelegram

    def register(
        self,
        book_id: str = "bk-lighthouse",
        title: str = "The Lighthouse Case",
        answers: dict[str, list[str]] | None = None,
        codes: list[str] | None = None,
        answer_type: str = "culprit_name",
        **extra: Any,
    ) -> dict[str, Any]:
        answers = answers or {"culprit_name": ["Captain Reed", "Reed", "Elias Reed"]}
        payload = {
            "book_id": book_id,
            "sku": f"HSP-ADULT-PZL-PBK-{abs(hash(book_id)) % 9999:04d}-SGL",
            "title": title,
            "answer_type": answer_type,
            "answers": {
                k: [answer_hash(KEY, book_id, k, v) for v in vs] for k, vs in answers.items()
            },
            "book_code_batches": [
                {
                    "batch_id": "b1",
                    "channel": "print",
                    "code_hashes": [code_hash(KEY, book_id, c) for c in codes or []],
                }
            ],
            "etsy_listing_ids": [f"L-{book_id}"],
            "shopify_product_ids": [f"gid://shopify/Product/{book_id}"],
            **extra,
        }
        r = self.client.post(
            "/api/admin/books", json=payload, headers={"Authorization": f"Bearer {TOKEN}"}
        )
        assert r.status_code == 200, r.text
        return dict(r.json())

    def solve(self, book_id: str = "bk-lighthouse", **kw: Any) -> Any:
        form = {
            "culprit_name": "Captain Reed",
            "purchase_place": "etsy",
            "proof": "1001",
            "email": "ann@example.com",
            "country": "US",
            "newsletter": "1",
            "terms": "1",
            "cf-turnstile-response": "ok",
        }
        form.update({k: v for k, v in kw.items() if v is not None})
        for k in [k for k, v in kw.items() if v is None]:
            form.pop(k, None)
        r = self.client.post(f"/solve/{book_id}", data=form)
        self.vault.process_outbox()
        return r


@pytest.fixture
def env(tmp_path: Any) -> Env:
    rules = load_rules()
    s = Settings(
        database_url=f"sqlite:///{tmp_path}/cv.db",
        public_url="https://cv.test",
        secret_key="s3cret",
        admin_api_token=TOKEN,
        answer_key=KEY,
        shopify_store_url="https://shop.test",
        etsy_shop_url="https://etsy.test/shop",
        secure_cookies=False,
        rules=rules,
    )
    fakes = FakeEtsy(), FakeShopify(), FakeKlaviyo(), FakeTelegram()
    prov = Providers(fakes[0], fakes[1], fakes[2], fakes[3], FakeCaptcha())
    app = create_app(s, prov, T.make_engine(s.database_url))
    return Env(TestClient(app), app.state.vault, *fakes)
