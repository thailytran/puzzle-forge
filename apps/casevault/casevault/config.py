"""Settings: secrets from the environment (.env on the server), rules from config/casevault.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_RULES = HERE.parent / "config" / "casevault.yaml"


def load_rules(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path or os.environ.get("CASEVAULT_CONFIG") or DEFAULT_RULES)
    return dict(yaml.safe_load(p.read_text(encoding="utf-8")))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    database_url: str = "sqlite:///data/casevault.db"
    public_url: str = "http://localhost:8000"
    secret_key: str = "dev-secret-change-me"
    admin_api_token: str = ""
    answer_key: str = ""
    turnstile_site_key: str = ""
    turnstile_secret: str = ""
    klaviyo_api_key: str = ""
    klaviyo_list_id: str = ""
    shopify_shop: str = ""  # <name>.myshopify.com
    shopify_token: str = ""
    shopify_api_version: str = "2026-01"
    shopify_store_url: str = ""  # where customers use Shopify coupons
    etsy_api_key: str = ""
    etsy_shop_id: str = ""
    etsy_token_file: str = "data/etsy_token.json"
    etsy_shop_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    secure_cookies: bool = True
    trust_cloudflare: bool = False
    rules: dict[str, Any] = field(default_factory=load_rules)

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=_env("DATABASE_URL", "sqlite:///data/casevault.db"),
            public_url=_env("PUBLIC_URL", "http://localhost:8000").rstrip("/"),
            secret_key=_env("SECRET_KEY") or "dev-secret-change-me",
            admin_api_token=_env("VAULT_ADMIN_TOKEN"),
            answer_key=_env("VAULT_ANSWER_KEY"),
            turnstile_site_key=_env("TURNSTILE_SITE_KEY"),
            turnstile_secret=_env("TURNSTILE_SECRET"),
            klaviyo_api_key=_env("KLAVIYO_API_KEY"),
            klaviyo_list_id=_env("KLAVIYO_LIST_ID"),
            shopify_shop=_env("SHOPIFY_SHOP"),
            shopify_token=_env("SHOPIFY_ADMIN_TOKEN"),
            shopify_api_version=_env("SHOPIFY_API_VERSION", "2026-01"),
            shopify_store_url=_env("SHOPIFY_STORE_URL"),
            etsy_api_key=_env("ETSY_API_KEY"),
            etsy_shop_id=_env("ETSY_SHOP_ID"),
            etsy_token_file=_env("ETSY_TOKEN_FILE", "data/etsy_token.json"),
            etsy_shop_url=_env("ETSY_SHOP_URL"),
            telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            secure_cookies=_env("SECURE_COOKIES", "1") != "0",
            trust_cloudflare=_env("TRUST_CLOUDFLARE", "0") == "1",
        )

    @property
    def site_name(self) -> str:
        return str(self.rules.get("site_name", "Case Vault"))

    def region_of(self, country: str) -> str:
        c = country.upper()
        for region, codes in self.rules["consent"]["regions"].items():
            if c in codes:
                return str(region)
        return "default"

    def newsletter_required(self, country: str) -> bool:
        rules = self.rules["consent"]["required_by_region"]
        return str(rules.get(self.region_of(country), rules["default"])) == "required"
