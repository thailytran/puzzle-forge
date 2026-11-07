"""FastAPI app: public form (HTMX), account (magic link), certificate, admin (password + TOTP),
admin API for Puzzle Forge (Bearer token)."""

from __future__ import annotations

import csv
import hmac
import io
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine, select

from casevault import db as T
from casevault.certificate import certificate_pdf
from casevault.config import Settings
from casevault.providers import Providers
from casevault.security import check_password, check_totp, sign, unsign
from casevault.service import PLACES, Submission, Vault, answer_fields, norm_email

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
PLACE_LABELS = {
    "etsy": "Etsy",
    "shopify": "Our online shop (Shopify)",
    "in_person": "In person",
    "gift": "It was a gift",
    "other": "Other",
}
COUNTRIES = [
    "US",
    "CA",
    "GB",
    "AU",
    "NZ",
    "IE",
    "DE",
    "FR",
    "NL",
    "BE",
    "AT",
    "CH",
    "ES",
    "IT",
    "PT",
    "SE",
    "NO",
    "DK",
    "FI",
    "IS",
    "PL",
    "CZ",
    "SK",
    "HU",
    "RO",
    "BG",
    "GR",
    "HR",
    "SI",
    "EE",
    "LV",
    "LT",
    "LU",
    "MT",
    "CY",
    "LI",
    "VN",
    "SG",
    "JP",
    "KR",
    "IN",
    "ZA",
    "BR",
    "MX",
    "AR",
    "OTHER",
]


def create_app(
    settings: Settings | None = None,
    providers: Providers | None = None,
    engine: Engine | None = None,
) -> FastAPI:
    s = settings or Settings.from_env()
    eng = engine or T.make_engine(s.database_url)
    vault = Vault(s, eng, providers or Providers.real(s))
    app = FastAPI(title=s.site_name, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.vault = vault

    def page(req: Request, name: str, ctx: dict[str, Any], status: int = 200) -> HTMLResponse:
        base = {"site": s.site_name, "public_url": s.public_url}
        return TEMPLATES.TemplateResponse(req, name, {**base, **ctx}, status_code=status)

    def client_ip(req: Request) -> str:
        for h in ("cf-connecting-ip", "x-real-ip"):
            if req.headers.get(h):
                return req.headers[h]
        return req.client.host if req.client else ""

    # ----------------------------------------------------------------- public
    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        missing = [
            k
            for k, v in {
                "VAULT_ADMIN_TOKEN": s.admin_api_token,
                "VAULT_ANSWER_KEY": s.answer_key,
                "TURNSTILE_SECRET": s.turnstile_secret,
                "KLAVIYO_API_KEY": s.klaviyo_api_key,
            }.items()
            if not v
        ]
        if s.secret_key == "dev-secret-change-me":
            missing.append("SECRET_KEY")
        return {"ok": True, "missing_config": missing}

    @app.get("/", response_class=HTMLResponse)
    def home(req: Request) -> HTMLResponse:
        return page(req, "home.html", {"books": vault.books()})

    def form_ctx(book: dict[str, Any], req: Request, **extra: Any) -> dict[str, Any]:
        country = (req.headers.get("cf-ipcountry") or "").upper()
        return {
            "book": book,
            "fields": answer_fields(book["answer_type"]),
            "places": [(p, PLACE_LABELS[p]) for p in PLACES],
            "countries": COUNTRIES,
            "country": country if country in COUNTRIES else "",
            "consent": s.rules["consent"],
            "optional_regions": [
                r for r, v in s.rules["consent"]["required_by_region"].items() if v == "optional"
            ],
            "region_codes": s.rules["consent"]["regions"],
            "turnstile_site_key": s.turnstile_site_key,
            "form_version": s.rules.get("form_version", 1),
            "errors": {},
            "values": {},
            **extra,
        }

    @app.get("/solve/{book_id}", response_class=HTMLResponse)
    def solve_form(req: Request, book_id: str, code: str = "") -> HTMLResponse:
        book = vault.book(book_id)
        if not book or not book["active"]:
            raise HTTPException(404, "Unknown book")
        values = {"proof": code, "purchase_place": "in_person" if code else ""}
        return page(req, "solve.html", form_ctx(book, req, values=values))

    @app.post("/solve/{book_id}", response_class=HTMLResponse)
    def solve_submit(
        req: Request,
        bg: BackgroundTasks,
        book_id: str,
        culprit_name: str = Form(""),
        unlock_code: str = Form(""),
        purchase_place: str = Form(""),
        proof: str = Form(""),
        email: str = Form(""),
        name: str = Form(""),
        country: str = Form(""),
        newsletter: str = Form(""),
        terms: str = Form(""),
        coupon_platform: str = Form(""),
        cf_turnstile_response: str = Form("", alias="cf-turnstile-response"),
    ) -> HTMLResponse:
        book = vault.book(book_id)
        if not book:
            raise HTTPException(404, "Unknown book")
        sub = Submission(
            book_id=book_id,
            answers={"culprit_name": culprit_name, "unlock_code": unlock_code},
            purchase_place=purchase_place,
            proof=proof,
            email=email,
            name=name,
            country=country if country != "OTHER" else "ZZ",
            newsletter=bool(newsletter),
            terms=bool(terms),
            coupon_platform=coupon_platform,
            captcha_token=cf_turnstile_response,
            ip=client_ip(req),
        )
        out = vault.submit(sub)
        bg.add_task(vault.process_outbox)
        if out.status == "invalid":
            values = {k: v for k, v in sub.__dict__.items() if isinstance(v, str)}
            values |= sub.answers
            ctx = form_ctx(book, req, errors=out.errors, values=values, message=out.message)
            return page(req, "solve.html", ctx, status=422)
        account = vault.account(sub.email) if out.status in ("approved", "duplicate") else None
        return page(req, "result.html", {"book": book, "out": out, "account": account})

    @app.get("/terms", response_class=HTMLResponse)
    def terms(req: Request) -> HTMLResponse:
        return page(req, "legal.html", {"kind": "terms"})

    @app.get("/privacy", response_class=HTMLResponse)
    def privacy(req: Request) -> HTMLResponse:
        return page(req, "legal.html", {"kind": "privacy"})

    @app.get("/certificate/{sid}.pdf")
    def certificate(sid: int, t: str = "") -> Response:
        data = unsign(s.secret_key, t, "cert")
        if not data or data.get("sid") != sid:
            raise HTTPException(403, "Invalid link")
        with eng.connect() as c:
            row = (
                c.execute(
                    select(T.solves, T.books.c.title, T.customers.c.name)
                    .join(T.books, T.books.c.book_id == T.solves.c.book_id)
                    .outerjoin(T.customers, T.customers.c.email == T.solves.c.email)
                    .where(T.solves.c.id == sid)
                )
                .mappings()
                .first()
            )
        if not row or row["status"] != "approved":
            raise HTTPException(404, "No certificate")
        pdf = certificate_pdf(
            s.site_name, row["name"] or "", row["title"], row["at"].date().isoformat(), sid
        )
        return Response(pdf, media_type="application/pdf")

    # ----------------------------------------------------------------- account (magic link)
    @app.get("/account", response_class=HTMLResponse)
    def account(req: Request, t: str = "") -> Response:
        if t:
            data = unsign(s.secret_key, t, "login")
            if not data:
                return page(req, "login.html", {"message": "This link has expired."}, 400)
            resp = RedirectResponse("/account", 303)
            cookie = sign(s.secret_key, {"email": data["email"]}, 7 * 86400, "session")
            resp.set_cookie(
                "cv_session",
                cookie,
                httponly=True,
                secure=s.secure_cookies,
                samesite="lax",
                max_age=7 * 86400,
            )
            return resp
        sess = unsign(s.secret_key, req.cookies.get("cv_session", ""), "session")
        if not sess:
            return page(req, "login.html", {})
        return page(
            req, "account.html", {"a": vault.account(sess["email"]), "books": vault.books()}
        )

    @app.post("/account/login", response_class=HTMLResponse)
    def login_link(req: Request, bg: BackgroundTasks, email: str = Form("")) -> HTMLResponse:
        e = norm_email(email)
        with eng.begin() as c:
            known = c.execute(select(T.customers.c.email).where(T.customers.c.email == e)).first()
            if known and vault._hits(c, f"login|{e}", 60) < 5:
                vault._hit(c, f"login|{e}")
                vault._event(c, "Login Link", e, {"login_url": vault.account_link(e)})
        bg.add_task(vault.process_outbox)
        msg = "If this e-mail has solved a case, a login link is on its way."
        return page(req, "login.html", {"message": msg})

    @app.post("/account/gift/{rid}", response_class=HTMLResponse)
    def gift(req: Request, bg: BackgroundTasks, rid: int, book_id: str = Form("")) -> Response:
        sess = unsign(s.secret_key, req.cookies.get("cv_session", ""), "session")
        if not sess:
            return RedirectResponse("/account", 303)
        try:
            vault.choose_gift(sess["email"], rid, book_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        bg.add_task(vault.process_outbox)
        return RedirectResponse("/account", 303)

    @app.get("/unsubscribe", response_class=HTMLResponse)
    def unsubscribe(req: Request, t: str = "") -> HTMLResponse:
        data = unsign(s.secret_key, t, "unsub")
        if not data:
            raise HTTPException(400, "Invalid link")
        vault.unsubscribe(data["email"])
        return page(
            req,
            "message.html",
            {
                "title": "Unsubscribed",
                "text": "You will no longer receive the newsletter. Your coupons stay valid "
                "and you will "
                "still get reward e-mails for cases you solve.",
            },
        )

    # ----------------------------------------------------------------- admin API (Puzzle Forge)
    def api_auth(authorization: str = Header("")) -> None:
        tok = authorization.removeprefix("Bearer ").strip()
        if not s.admin_api_token or not hmac.compare_digest(tok, s.admin_api_token):
            raise HTTPException(401, "bad token")

    @app.post("/api/admin/books", dependencies=[Depends(api_auth)])
    async def api_register(req: Request, bg: BackgroundTasks) -> dict[str, Any]:
        try:
            out = vault.register_book(await req.json())
        except (KeyError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        with eng.begin() as c:
            vault._enqueue(c, "telegram", {"text": f"Book registered: {out['book_id']}"})
        bg.add_task(vault.process_outbox)
        return out

    @app.get("/api/admin/books/{book_id}", dependencies=[Depends(api_auth)])
    def api_book(book_id: str) -> dict[str, Any]:
        b = vault.book(book_id)
        if not b:
            raise HTTPException(404, "unknown book")
        return {k: v for k, v in b.items() if k != "cover_png_b64"} | {
            "registered_at": str(b["registered_at"]),
            "updated_at": str(b["updated_at"]),
        }

    # ----------------------------------------------------------------- admin UI
    def admin_user(req: Request) -> str:
        sess = unsign(s.secret_key, req.cookies.get("cv_admin", ""), "admin")
        if not sess:
            raise HTTPException(303, headers={"Location": "/admin/login"})
        return str(sess["user"])

    @app.get("/admin/login", response_class=HTMLResponse)
    def admin_login_form(req: Request) -> HTMLResponse:
        return page(req, "admin/login.html", {})

    @app.post("/admin/login", response_class=HTMLResponse)
    def admin_login(
        req: Request, username: str = Form(""), password: str = Form(""), otp: str = Form("")
    ) -> Response:
        ip = client_ip(req)
        with eng.begin() as c:
            if vault._hits(c, f"admin|{ip}", 15) >= 5:
                return page(req, "admin/login.html", {"message": "Locked for 15 minutes."}, 429)
            row = (
                c.execute(select(T.admins).where(T.admins.c.username == username))
                .mappings()
                .first()
            )
            ok = bool(
                row
                and check_password(password, row["password_hash"])
                and check_totp(row["totp_secret"], otp)
            )
            if not ok:
                vault._hit(c, f"admin|{ip}")
                vault._fraud(c, "admin_login_failed", "", ip, username=username)
                return page(req, "admin/login.html", {"message": "Wrong login."}, 401)
        resp = RedirectResponse("/admin", 303)
        resp.set_cookie(
            "cv_admin",
            sign(s.secret_key, {"user": username}, 8 * 3600, "admin"),
            httponly=True,
            secure=s.secure_cookies,
            samesite="strict",
        )
        return resp

    @app.get("/admin/logout")
    def admin_logout() -> Response:
        resp = RedirectResponse("/admin/login", 303)
        resp.delete_cookie("cv_admin")
        return resp

    def rows(q: Any) -> list[dict[str, Any]]:
        with eng.connect() as c:
            return [dict(r) for r in c.execute(q).mappings()]

    @app.get("/admin", response_class=HTMLResponse)
    def admin_home(req: Request, user: str = Depends(admin_user)) -> HTMLResponse:
        pool = {p: 0 for p in s.rules["rewards"]["tiers"].values()}
        with eng.connect() as c:
            for p in pool:
                pool[p] = vault.pool_left(c, int(p))
        return page(
            req,
            "admin/home.html",
            {
                "user": user,
                "stats": vault.stats(),
                "pool": pool,
                "outbox": rows(
                    select(T.outbox)
                    .where(T.outbox.c.status != "done")
                    .order_by(T.outbox.c.id.desc())
                    .limit(50)
                ),
            },
        )

    @app.get("/admin/solves", response_class=HTMLResponse)
    def admin_solves(
        req: Request, status: str = "", user: str = Depends(admin_user)
    ) -> HTMLResponse:
        q = select(T.solves).order_by(T.solves.c.id.desc()).limit(500)
        if status:
            q = q.where(T.solves.c.status == status)
        return page(req, "admin/solves.html", {"user": user, "solves": rows(q), "status": status})

    @app.post("/admin/solves/{sid}")
    def admin_decide(
        sid: int,
        bg: BackgroundTasks,
        action: str = Form(""),
        note: str = Form(""),
        user: str = Depends(admin_user),
    ) -> Response:
        try:
            vault.decide_pending(sid, action == "approve", note or f"by {user}")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        bg.add_task(vault.process_outbox)
        return RedirectResponse("/admin/solves?status=pending", 303)

    @app.get("/admin/customers", response_class=HTMLResponse)
    def admin_customers(req: Request, user: str = Depends(admin_user)) -> HTMLResponse:
        return page(
            req,
            "admin/customers.html",
            {
                "user": user,
                "customers": rows(
                    select(T.customers).order_by(T.customers.c.created_at.desc()).limit(1000)
                ),
            },
        )

    @app.get("/admin/fraud", response_class=HTMLResponse)
    def admin_fraud(req: Request, user: str = Depends(admin_user)) -> HTMLResponse:
        return page(
            req,
            "admin/fraud.html",
            {
                "user": user,
                "items": rows(select(T.fraud_log).order_by(T.fraud_log.c.id.desc()).limit(500)),
            },
        )

    @app.get("/admin/rewards", response_class=HTMLResponse)
    def admin_rewards(req: Request, user: str = Depends(admin_user)) -> HTMLResponse:
        return page(
            req,
            "admin/rewards.html",
            {
                "user": user,
                "items": rows(select(T.rewards).order_by(T.rewards.c.id.desc()).limit(500)),
            },
        )

    @app.post("/admin/import/etsy-orders")
    async def admin_import_orders(
        req: Request, bg: BackgroundTasks, user: str = Depends(admin_user)
    ) -> Response:
        form = await req.form()
        f = form.get("file")
        text = (await f.read()).decode("utf-8-sig") if hasattr(f, "read") else str(f or "")
        res = vault.import_etsy_csv(text)
        bg.add_task(vault.process_outbox)
        return PlainTextResponse(f"imported: {res}")

    @app.post("/admin/import/etsy-coupons")
    async def admin_import_pool(req: Request, user: str = Depends(admin_user)) -> Response:
        form = await req.form()
        f = form.get("file")
        text = (await f.read()).decode("utf-8-sig") if hasattr(f, "read") else str(f or "")
        return PlainTextResponse(f"imported {vault.import_pool_csv(text)} codes")

    @app.get("/admin/export/newsletter.csv")
    def admin_export(user: str = Depends(admin_user)) -> Response:
        buf = io.StringIO()
        data = vault.consenting_emails()
        w = csv.DictWriter(
            buf, fieldnames=["email", "name", "country", "consented_at", "ip", "form_version"]
        )
        w.writeheader()
        w.writerows(data)
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=newsletter.csv"},
        )

    return app


def app_factory() -> FastAPI:  # uvicorn casevault.web:app_factory --factory
    return create_app()
