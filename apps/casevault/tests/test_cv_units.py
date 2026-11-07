import json
from datetime import datetime

import httpx
import pytest
from casevault import bookcode
from casevault.answers import answer_hash, normalize
from casevault.certificate import certificate_pdf
from casevault.config import Settings, load_rules
from casevault.providers import EtsyApi, KlaviyoApi, ShopifyAdmin, Turnstile
from casevault.security import check_password, check_totp, hash_password, sign, totp, unsign


def test_bookcode_checksum_catches_typos_and_swaps():
    code = bookcode.new_code()
    assert bookcode.is_valid(code) and bookcode.is_valid(bookcode.pretty(code).lower())
    assert not set(code) & set("01OI")
    for i in range(len(code)):
        for ch in bookcode.ALPHABET:
            if ch != code[i]:
                assert not bookcode.is_valid(code[:i] + ch + code[i + 1 :])
    for i in range(len(code) - 1):
        if code[i] != code[i + 1]:
            swapped = code[:i] + code[i + 1] + code[i] + code[i + 2 :]
            assert not bookcode.is_valid(swapped)


def test_normalize():
    assert normalize("culprit_name", " Captain  Réed! ") == "captainreed"
    assert normalize("unlock_code", "04 - 72") == "0472"
    assert answer_hash("k", "b", "culprit_name", "REED") == answer_hash(
        "k", "b", "culprit_name", "reed"
    )
    assert answer_hash("k", "b", "culprit_name", "reed") != answer_hash(
        "k", "b2", "culprit_name", "reed"
    )


def test_totp_rfc6238_vector_and_passwords():
    import base64

    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp(secret, at=59, digits=8) == "94287082"
    assert check_totp(secret, totp(secret, at=1000), at=1010)
    h = hash_password("correct horse")
    assert check_password("correct horse", h) and not check_password("x", h)


def test_signed_tokens():
    t = sign("k", {"a": 1}, 60, "p")
    assert unsign("k", t, "p") == {"a": 1}
    assert unsign("k", t, "other") is None and unsign("k2", t, "p") is None
    assert unsign("k", sign("k", {"a": 1}, -5, "p"), "p") is None


def test_certificate_pdf():
    pdf = certificate_pdf("Case Vault", "Zoë (Z)", "The Lighthouse Case", "2026-11-07", 7)
    assert pdf.startswith(b"%PDF-1.4") and b"startxref" in pdf and b"\\(Z\\)" in pdf


def settings(**kw):
    return Settings(rules=load_rules(), **kw)


def test_klaviyo_event_payload_shape():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(202)

    k = KlaviyoApi(
        settings(klaviyo_api_key="pk_x", klaviyo_list_id="L1"), httpx.MockTransport(handler)
    )
    k.event("Case Solved", "a@b.co", {"reward_tier": 1}, "u1")
    k.subscribe("a@b.co", datetime(2026, 11, 7), "form v1")
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/api/events"
    assert seen[0].headers["Authorization"] == "Klaviyo-API-Key pk_x"
    assert body["data"]["attributes"]["metric"]["data"]["attributes"]["name"] == "Case Solved"
    sub = json.loads(seen[1].content)["data"]
    assert sub["relationships"]["list"]["data"]["id"] == "L1"
    prof = sub["attributes"]["profiles"]["data"][0]["attributes"]
    assert prof["subscriptions"]["email"]["marketing"]["consent"] == "SUBSCRIBED"


def test_klaviyo_error_raises():
    k = KlaviyoApi(
        settings(klaviyo_api_key="pk"), httpx.MockTransport(lambda r: httpx.Response(500))
    )
    with pytest.raises(Exception, match="HTTP 500"):
        k.event("x", "a@b.co", {}, "u")


def test_shopify_discount_and_order_lookup():
    seen = []

    def handler(req):
        q = json.loads(req.content)
        seen.append(q)
        if "orders" in q["query"]:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "orders": {
                            "nodes": [
                                {
                                    "id": "o",
                                    "name": "#1",
                                    "lineItems": {
                                        "nodes": [
                                            {"title": "T", "sku": "S", "product": {"id": "P1"}}
                                        ]
                                    },
                                }
                            ]
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "discountCodeBasicCreate": {"codeDiscountNode": {"id": "d"}, "userErrors": []}
                }
            },
        )

    s = ShopifyAdmin(
        settings(shopify_shop="x.myshopify.com", shopify_token="t"), httpx.MockTransport(handler)
    )
    look = s.find_order("1")
    assert look.status == "found" and look.lines[0]["product_id"] == "P1"
    assert seen[0]["variables"]["q"] == "name:#1"
    s.create_discount("CV-X", 20, datetime(2027, 2, 5), None, "t")
    d = seen[1]["variables"]["d"]
    assert d["usageLimit"] == 1 and d["customerGets"]["value"]["percentage"] == 0.2
    assert d["combinesWith"] == {
        "orderDiscounts": False,
        "productDiscounts": False,
        "shippingDiscounts": False,
    }


def test_etsy_lookup(tmp_path):
    tok = tmp_path / "t.json"
    tok.write_text(json.dumps({"access_token": "A", "refresh_token": "R", "expires_at": 9e12}))

    def handler(req):
        if req.url.path.endswith("/receipts/404"):
            return httpx.Response(404)
        assert req.headers["x-api-key"] == "key" and req.headers["Authorization"] == "Bearer A"
        return httpx.Response(
            200,
            json={
                "receipt_id": 5,
                "transactions": [{"listing_id": 77, "title": "Book", "sku": None}],
            },
        )

    e = EtsyApi(
        settings(etsy_api_key="key", etsy_shop_id="9", etsy_token_file=str(tok)),
        httpx.MockTransport(handler),
    )
    assert e.lookup("5").lines == [{"listing_id": "77", "title": "Book", "sku": ""}]
    assert e.lookup("404").status == "not_found"
    assert EtsyApi(settings()).lookup("5").status == "unavailable"


def test_turnstile():
    t = Turnstile(
        settings(turnstile_secret="s"),
        httpx.MockTransport(lambda r: httpx.Response(200, json={"success": False})),
    )
    assert t.verify("x", "1.2.3.4") is False
    assert Turnstile(settings()).verify("", "") is True


def test_region_rules():
    s = settings()
    assert s.newsletter_required("US") and s.newsletter_required("CA")
    assert not s.newsletter_required("DE") and not s.newsletter_required("gb")
