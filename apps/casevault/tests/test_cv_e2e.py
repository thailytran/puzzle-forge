"""End-to-end flows (Etsy / Shopify / Klaviyo mocked) — docs/CASEVAULT.md, owner list 2026-11-07."""

from __future__ import annotations

import re
from datetime import timedelta

from casevault import bookcode
from casevault import db as T
from casevault.security import new_totp_secret, totp
from sqlalchemy import select, update

POOL = "percent,code,expires\n" + "\n".join(
    f"{p},ETSY{p}-{i:02d}," for p in (10, 20, 30, 40) for i in range(25)
)


def etsy_receipt(env, order, *book_ids):
    env.etsy.receipts[order] = [{"listing_id": f"L-{b}", "title": b, "sku": ""} for b in book_ids]


def test_approved_book_appears_and_correct_answer_mails_10_percent(env):
    out = env.register()
    assert out["url"] == "https://cv.test/solve/bk-lighthouse"
    assert "The Lighthouse Case" in env.client.get("/").text
    assert env.client.get("/solve/bk-lighthouse").status_code == 200
    env.vault.import_pool_csv(POOL)
    etsy_receipt(env, "1001", "bk-lighthouse")
    r = env.solve(culprit_name="  elias reed! ")
    assert r.status_code == 200 and "Case solved" in r.text
    ev = env.klaviyo.named("Case Solved", "ann@example.com")
    assert len(ev) == 1
    e = ev[0]
    assert e["reward_percent"] == 10 and e["reward_tier"] == 1 and e["coupon_platform"] == "etsy"
    assert e["coupon_code"].startswith("ETSY10-") and e["coupon_where"] == "https://etsy.test/shop"
    assert e["progress_text"] == "1/5 cases solved – 4 more to earn a FREE book"
    assert e["certificate_url"].startswith("https://cv.test/certificate/")
    assert env.klaviyo.profiles["ann@example.com"]["cases_solved"] == 1
    assert "ann@example.com" in env.klaviyo.subscribed
    assert any("Case solved" in m for m in env.telegram.messages)
    pdf = env.client.get(e["certificate_url"].removeprefix("https://cv.test"))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_same_email_five_books_gets_10_20_30_40_then_gift_then_cycle(env):
    codes = {}
    for i in range(1, 7):
        codes[i] = bookcode.new_code()
        env.register(book_id=f"bk{i}", title=f"Case {i}", codes=[codes[i]])
    got = []
    for i in range(1, 7):
        r = env.solve(
            book_id=f"bk{i}",
            purchase_place="in_person",
            proof=bookcode.pretty(codes[i]).lower(),
            email="Bob@Example.com ",
        )
        assert r.status_code == 200, r.text
        ev = env.klaviyo.named("Case Solved", "bob@example.com")[-1]
        got.append((ev["reward_tier"], ev["reward_percent"], ev["is_gift"]))
    assert got == [
        (1, 10, False),
        (2, 20, False),
        (3, 30, False),
        (4, 40, False),
        (5, 100, True),
        (1, 10, False),
    ]
    assert [d["percent"] for d in env.shopify.discounts] == [10, 20, 30, 40, 10]
    # milestone gift: the customer chooses a digital book -> 100 % Shopify code for that product
    acc = env.vault.account("bob@example.com")
    gift = next(r for r in acc["rewards"] if r["tier"] == 5)
    r = env.vault.choose_gift("bob@example.com", gift["id"], "bk3")
    assert r["status"] == "issued" and r["code"].startswith("CV-")
    assert env.shopify.discounts[-1]["percent"] == 100
    assert env.shopify.discounts[-1]["product_id"] == "gid://shopify/Product/bk3"
    env.vault.process_outbox()
    assert env.klaviyo.named("Gift Ready", "bob@example.com")
    assert acc["count"] == 6


def test_etsy_order_number_is_required(env):
    env.register()
    r = env.solve(proof="")
    assert r.status_code == 422 and "Etsy order number is required" in r.text


def test_etsy_order_not_in_shop_or_without_the_book_is_rejected(env):
    env.register()
    env.register(book_id="bk-other", title="Other Case")
    r = env.solve(proof="9999")  # API: not this shop
    assert "could not find this order" in r.text
    etsy_receipt(env, "2002", "bk-other")
    r = env.solve(proof="2002", email="c@example.com")
    assert "does not contain this book" in r.text
    assert not env.klaviyo.named("Case Solved")


def test_etsy_order_pending_until_csv_import_then_auto_approved(env):
    env.etsy.available = False  # no Etsy API access yet -> CSV only
    env.register()
    env.vault.import_pool_csv(POOL)
    r = env.solve(proof="#3003", email="dee@example.com")
    assert "verify your order" in r.text
    assert env.klaviyo.named("Verification Pending", "dee@example.com")
    assert not env.klaviyo.named("Case Solved", "dee@example.com")
    csv_text = (
        "Sale Date,Item Name,Buyer,Quantity,Order ID,Listing ID\n"
        "11/07/2026,The Lighthouse Case - Escape Book,dee,1,3003,L-bk-lighthouse\n"
    )
    res = env.vault.import_etsy_csv(csv_text)
    env.vault.process_outbox()
    assert res["approved"] == 1
    assert env.klaviyo.named("Verification Approved", "dee@example.com")
    ev = env.klaviyo.named("Case Solved", "dee@example.com")
    assert ev and ev[0]["reward_percent"] == 10


def test_pending_too_long_is_rejected(env):
    env.etsy.available = False
    env.register()
    env.solve(proof="4004", email="old@example.com")
    with env.vault.e.begin() as c:
        c.execute(update(T.solves).values(at=T.now() - timedelta(days=60)))
    assert env.vault.recheck_pending()["rejected"] == 1


def test_book_code_and_order_reused_by_second_email_are_rejected(env):
    code = bookcode.new_code()
    env.register(codes=[code])
    r = env.solve(purchase_place="gift", proof=code, email="first@example.com")
    assert "Case solved" in r.text
    r = env.solve(purchase_place="gift", proof=code, email="second@example.com")
    assert "already used with another e-mail" in r.text
    etsy_receipt(env, "5005", "bk-lighthouse")
    env.solve(proof="5005", email="third@example.com", coupon_platform="shopify")
    r = env.solve(proof="5005", email="fourth@example.com")
    assert "already used with another e-mail" in r.text
    with env.vault.e.connect() as c:
        kinds = [r[0] for r in c.execute(select(T.fraud_log.c.kind))]
    assert kinds.count("proof_reuse") == 2


def test_multi_book_etsy_order_counts_each_book(env):
    env.register(book_id="a1", title="Case A")
    env.register(book_id="a2", title="Case B")
    etsy_receipt(env, "6006", "a1", "a2")
    for b in ("a1", "a2"):
        assert "Case solved" in env.solve(book_id=b, proof="6006", coupon_platform="shopify").text
    r = env.solve(book_id="a1", proof="6006", coupon_platform="shopify")
    assert "already solved" in r.text
    assert env.vault.account("ann@example.com")["count"] == 2


def test_newsletter_required_us_optional_eu_and_unsubscribe_keeps_coupons(env):
    env.register()
    etsy_receipt(env, "7007", "bk-lighthouse")
    r = env.solve(proof="7007", newsletter=None, country="US")
    assert r.status_code == 422 and "tick the newsletter box" in r.text
    r = env.solve(
        proof="7007",
        newsletter=None,
        country="DE",
        email="eu@example.com",
        coupon_platform="shopify",
    )
    assert "Case solved" in r.text
    assert "eu@example.com" not in env.klaviyo.subscribed
    # a US customer subscribes, solves, then unsubscribes: the coupon stays, mails still come
    env.register(book_id="bk2", title="Second Case")
    etsy_receipt(env, "7008", "bk-lighthouse", "bk2")
    env.solve(proof="7008", email="us@example.com", coupon_platform="shopify")
    assert "us@example.com" in env.klaviyo.subscribed
    env.vault.unsubscribe("us@example.com")
    env.vault.process_outbox()
    assert "us@example.com" not in env.klaviyo.subscribed
    acc = env.vault.account("us@example.com")
    assert acc["rewards"][0]["code"] and acc["rewards"][0]["status"] == "issued"
    emails = [e["email"] for e in env.vault.consenting_emails()]
    assert "us@example.com" not in emails and "eu@example.com" not in emails
    # next solve (US: box required again = a fresh, recorded consent) still gets its reward mail
    env.solve(book_id="bk2", proof="7008", email="us@example.com", coupon_platform="shopify")
    assert len(env.klaviyo.named("Case Solved", "us@example.com")) == 2


def test_wrong_answers_lock_out_and_numeric_codes_are_exact(env):
    env.register(answer_type="unlock_code", answers={"unlock_code": ["0472"]})
    etsy_receipt(env, "8008", "bk-lighthouse")
    r = env.solve(culprit_name=None, unlock_code="472", proof="8008")
    assert "not the answer" in r.text and "4 tries left" in r.text
    for _ in range(4):
        env.solve(culprit_name=None, unlock_code="1111", proof="8008")
    r = env.solve(culprit_name=None, unlock_code="0472", proof="8008")
    assert "Too many wrong answers" in r.text
    with env.vault.e.begin() as c:
        c.execute(T.attempts.delete())
    r = env.solve(culprit_name=None, unlock_code="04-72", proof="8008", coupon_platform="shopify")
    assert "Case solved" in r.text


def test_both_answers_needed(env):
    env.register(answer_type="both", answers={"culprit_name": ["Reed"], "unlock_code": ["47"]})
    etsy_receipt(env, "9009", "bk-lighthouse")
    assert "not the answer" in env.solve(culprit_name="Reed", unlock_code="48", proof="9009").text
    assert (
        "Case solved"
        in env.solve(
            culprit_name="reed", unlock_code="47", proof="9009", coupon_platform="shopify"
        ).text
    )


def test_shopify_order_proof(env):
    env.register()
    env.shopify.orders["1042"] = [
        {"product_id": "gid://shopify/Product/bk-lighthouse", "title": "x", "sku": ""}
    ]
    r = env.solve(purchase_place="shopify", proof="#1042")
    assert "Case solved" in r.text
    assert env.klaviyo.named("Case Solved")[0]["coupon_platform"] == "shopify"
    r = env.solve(purchase_place="shopify", proof="#1043", email="z@example.com")
    assert "could not find this Shopify order" in r.text


def test_klaviyo_down_never_loses_the_reward(env):
    env.register()
    etsy_receipt(env, "1111", "bk-lighthouse")
    env.klaviyo.fail = True
    r = env.solve(proof="1111", coupon_platform="shopify")
    assert "Case solved" in r.text and re.search(r"CV-[A-Z0-9]{8}", r.text)
    for _ in range(3):
        with env.vault.e.begin() as c:
            c.execute(update(T.outbox).values(next_at=T.now()))
        env.vault.process_outbox()
    assert any("failing" in m for m in env.telegram.messages)
    env.klaviyo.fail = False
    with env.vault.e.begin() as c:
        c.execute(update(T.outbox).values(next_at=T.now()))
    env.vault.process_outbox()
    assert env.klaviyo.named("Case Solved", "ann@example.com")


def test_shopify_down_coupon_issued_later(env):
    env.register()
    etsy_receipt(env, "1212", "bk-lighthouse")
    env.shopify.fail = True
    r = env.solve(proof="1212", coupon_platform="shopify")
    assert "being prepared" in r.text
    assert not env.klaviyo.named("Case Solved")
    env.shopify.fail = False
    with env.vault.e.begin() as c:
        c.execute(update(T.outbox).values(next_at=T.now()))
    env.vault.process_outbox()
    env.vault.process_outbox()
    assert env.klaviyo.named("Case Solved")[0]["coupon_code"].startswith("CV-")


def test_etsy_pool_low_stock_alert(env):
    env.register()
    env.vault.import_pool_csv("percent,code\n10,A1\n10,A2\n")
    etsy_receipt(env, "1313", "bk-lighthouse")
    env.solve(proof="1313")
    assert any("pool low: 1 left for 10%" in m for m in env.telegram.messages)


def test_rate_limit_per_ip(env):
    env.register()
    for i in range(30):
        env.solve(culprit_name="nobody", proof=str(20000 + i), email=f"u{i}@example.com")
    r = env.solve(proof="1", email="late@example.com")
    assert "Too many attempts" in r.text


def test_captcha_and_terms(env):
    env.register()
    r = env.solve(**{"cf-turnstile-response": "bad"})
    assert r.status_code == 422 and "Captcha" in r.text
    r = env.solve(terms=None)
    assert "accept the Terms" in r.text


def test_admin_login_2fa_pages_export_and_manual_approval(env):
    from casevault.security import hash_password
    from sqlalchemy import insert

    secret = new_totp_secret()
    with env.vault.e.begin() as c:
        c.execute(
            insert(T.admins).values(
                username="owner", password_hash=hash_password("pw-123456789"), totp_secret=secret
            )
        )
    c = env.client
    assert c.get("/admin", follow_redirects=False).status_code == 303
    bad = c.post(
        "/admin/login", data={"username": "owner", "password": "pw-123456789", "otp": "000000"}
    )
    assert bad.status_code == 401
    ok = c.post(
        "/admin/login",
        data={"username": "owner", "password": "pw-123456789", "otp": totp(secret)},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    env.etsy.available = False
    env.register()
    env.solve(proof="4242", email="p@example.com")
    for path in (
        "/admin",
        "/admin/solves?status=pending",
        "/admin/customers",
        "/admin/fraud",
        "/admin/rewards",
    ):
        assert c.get(path).status_code == 200, path
    sid = env.vault.account("p@example.com")
    with env.vault.e.connect() as conn:
        sid = conn.execute(select(T.solves.c.id).where(T.solves.c.status == "pending")).scalar_one()
    assert c.post(f"/admin/solves/{sid}", data={"action": "approve"}).status_code == 200
    env.vault.process_outbox()
    assert env.klaviyo.named("Verification Approved", "p@example.com")
    csv_text = c.get("/admin/export/newsletter.csv").text
    assert "p@example.com" in csv_text and "consented_at" in csv_text
    up = c.post("/admin/import/etsy-coupons", files={"file": ("c.csv", POOL.encode())})
    assert "imported 100" in up.text


def test_admin_api_needs_token(env):
    r = env.client.post("/api/admin/books", json={}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401
    r = env.client.post(
        "/api/admin/books",
        json={"book_id": "x", "title": "x", "answer_type": "culprit_name", "answers": {}},
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert r.status_code == 422


def test_account_magic_link(env):
    env.register()
    etsy_receipt(env, "1414", "bk-lighthouse")
    env.solve(proof="1414", coupon_platform="shopify")
    env.client.post("/account/login", data={"email": "ANN@example.com"})
    env.vault.process_outbox()
    link = env.klaviyo.named("Login Link", "ann@example.com")[0]["login_url"]
    r = env.client.get(link.removeprefix("https://cv.test"))
    assert r.status_code == 200 and "The Lighthouse Case" in r.text and "CV-" in r.text
    assert env.client.get("/account?t=forged.token").status_code == 400


def test_security_headers_errors_and_migrate(env, tmp_path):
    r = env.client.get("/healthz")
    assert r.headers["X-Frame-Options"] == "DENY" and "Strict-Transport-Security" in r.headers
    assert r.json()["version"]
    assert env.client.get("/admin/login").headers["Cache-Control"] == "no-store"
    # spoofed CF-Connecting-IP is ignored unless TRUST_CLOUDFLARE=1
    env.register()
    env.solve(culprit_name="wrong", **{"cf-turnstile-response": "ok"})
    with env.vault.e.connect() as c:
        ip = c.execute(select(T.solves.c.ip)).scalar_one()
    assert ip == "testclient"
    from casevault.migrations import migrate

    assert migrate(env.vault.e) == 1 and migrate(env.vault.e) == 1


def test_fraud_alert_goes_to_telegram(env):
    code = bookcode.new_code()
    env.register(codes=[code])
    env.solve(purchase_place="gift", proof=code, email="first@example.com")
    env.solve(purchase_place="gift", proof=code, email="second@example.com")
    env.vault.process_outbox()
    assert any("proof_reuse" in m for m in env.telegram.messages)
