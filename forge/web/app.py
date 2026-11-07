"""Forge web UI (owner only). Listens on 127.0.0.1 or the Tailscale IP (forge web refuses 0.0.0.0).

Pages (Vietnamese labels for the owner): dashboard, new book (form or CSV), book page (state,
QA report, files, approve/reject), settings (AI providers + routing + budget, SKU/Hub, Case Vault,
Telegram, backup, brand). JSON API under /api for HALOSPARK Studio later (P5.4)."""

from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from forge.config import Settings, get_settings
from forge.jobs import JobQueue
from forge.web.auth import check_password, make_cookie, read_cookie, session_key

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
ENV_KEYS = {  # editable in Settings (non-secret, written to the env file)
    "FORGE_SKU_PROVIDER": "SKU provider (hub | dev)",
    "HUB_URL": "Product Hub URL",
    "VAULT_URL": "Case Vault URL (prod)",
    "VAULT_DOMAIN": "Case Vault domain printed in books (prod)",
    "VAULT_STAGING_URL": "Case Vault URL (staging, or mock)",
    "VAULT_STAGING_DOMAIN": "Case Vault domain (staging)",
    "TELEGRAM_CHAT_ID": "Telegram chat id",
    "FORGE_BACKUP_REMOTE": "rclone remote for backups (e.g. gdrive:puzzle-forge-backups)",
}
SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "HALOSPARK_AI_TOKEN",
    "HUB_TOKEN",
    "VAULT_ADMIN_TOKEN",
    "VAULT_ANSWER_KEY",
    "VAULT_STAGING_ADMIN_TOKEN",
    "VAULT_STAGING_ANSWER_KEY",
    "TELEGRAM_BOT_TOKEN",
)
LINES = {  # book lines available now (more come with P3 / P8 blueprints)
    "classic_wordsearch": ("Word search", ["wordsearch"]),
    "classic_mixed": (
        "Mixed puzzles",
        ["wordsearch", "sudoku", "maze", "scramble", "cryptogram", "crossword"],
    ),
    "classic_sudoku": ("Sudoku", ["sudoku"]),
}
AUDIENCES = ("kids_6_8", "kids_9_12", "teen", "adult", "senior_large_print")
TRIMS = ("8.5x11", "8x10", "6x9", "8.5x8.5")


def spec_from_form(f: dict[str, str]) -> dict[str, Any]:
    line = f.get("line", "classic_wordsearch")
    if line not in LINES:
        raise ValueError(f"unknown book line {line!r}")
    types = [{"type": t} for t in LINES[line][1]]
    audience = f.get("audience", "adult")
    if audience not in AUDIENCES:
        raise ValueError("unknown audience")
    pages = int(f.get("content_pages") or 100)
    if not 4 <= pages <= 300:
        raise ValueError("content pages must be 4..300")
    spec: dict[str, Any] = {
        "book": {
            "title": f["title"].strip(),
            "subtitle": f.get("subtitle", "").strip(),
            "audience": audience,
            "trim": f.get("trim", "8.5x11"),
            "content_pages": pages,
            "seed": int(f.get("seed") or int(time.time()) % 100000),
        },
        "puzzles": {"mode": f.get("mode", "progressive"), "types": types},
    }
    if f.get("themes"):
        spec["puzzles"]["themes"] = [t.strip() for t in f["themes"].split(",") if t.strip()]
    if not spec["book"]["title"]:
        raise ValueError("title is required")
    return spec


def create_app(settings: Settings | None = None) -> FastAPI:
    st = settings or get_settings()
    app = FastAPI(title="Puzzle Forge", docs_url=None, redoc_url=None, openapi_url=None)
    key = session_key(st.config_dir)
    failures: dict[str, list[float]] = {}

    def page(req: Request, name: str, ctx: dict[str, Any], code: int = 200) -> HTMLResponse:
        from forge.version import version_line

        base = {"env": st.env, "version": version_line()}
        return TEMPLATES.TemplateResponse(req, name, {**base, **ctx}, status_code=code)

    def user(req: Request) -> str:
        u = read_cookie(key, req.cookies.get("forge_session", ""))
        if not u:
            raise HTTPException(303, headers={"Location": "/login"})
        return u

    def queue() -> JobQueue:
        return JobQueue(st.db_path)

    def book_dir(book_id: str) -> Path:
        d = (st.output_dir / book_id).resolve()
        if d.parent != st.output_dir.resolve() or not (d / "manifest.json").is_file():
            raise HTTPException(404, "unknown book")
        return d

    # ------------------------------------------------------------------ auth
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "env": st.env}

    @app.get("/login", response_class=HTMLResponse)
    def login_form(req: Request) -> HTMLResponse:
        return page(req, "login.html", {})

    @app.post("/login")
    def login(req: Request, password: str = Form("")) -> Response:
        ip = req.client.host if req.client else ""
        recent = [t for t in failures.get(ip, []) if t > time.time() - 900]
        if len(recent) >= 5:
            return page(
                req, "login.html", {"error": "Khoá 15 phút do sai mật khẩu nhiều lần."}, 429
            )
        stored = st.secret("FORGE_WEB_PASSWORD_HASH")
        if not stored:
            return page(
                req,
                "login.html",
                {"error": "Chưa đặt mật khẩu: chạy `forge web set-password` trên VM."},
                400,
            )
        if not check_password(password, stored):
            failures[ip] = [*recent, time.time()]
            return page(req, "login.html", {"error": "Sai mật khẩu."}, 401)
        resp = RedirectResponse("/", 303)
        resp.set_cookie(
            "forge_session",
            make_cookie(key, "owner"),
            httponly=True,
            samesite="strict",
            max_age=12 * 3600,
        )
        return resp

    @app.get("/logout")
    def logout() -> Response:
        resp = RedirectResponse("/login", 303)
        resp.delete_cookie("forge_session")
        return resp

    # ------------------------------------------------------------------ dashboard
    def books() -> list[dict[str, Any]]:
        from forge.qa.state import StateStore

        out = []
        if not st.output_dir.is_dir():
            return out
        with StateStore(st.db_path) as store:
            for d in sorted(st.output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                m = d / "manifest.json"
                if not m.is_file():
                    continue
                man = json.loads(m.read_text())
                bid = man["book_id"]
                out.append(
                    {
                        "book_id": bid,
                        "title": man["spec"]["book"]["title"],
                        "state": store.current(bid) or "DRAFT",
                        "pages": man.get("page_count", ""),
                    }
                )
        return out

    @app.get("/", response_class=HTMLResponse)
    def dashboard(req: Request, u: str = Depends(user)) -> HTMLResponse:
        q = queue()
        try:
            jobs, counts = q.recent(30), q.counts()
        finally:
            q.close()
        bs = books()
        by_state: dict[str, int] = {}
        for b in bs:
            by_state[b["state"]] = by_state.get(b["state"], 0) + 1
        return page(
            req,
            "dashboard.html",
            {"jobs": jobs, "counts": counts, "books": bs, "by_state": by_state},
        )

    # ------------------------------------------------------------------ new books
    @app.get("/new", response_class=HTMLResponse)
    def new_form(req: Request, u: str = Depends(user)) -> HTMLResponse:
        return page(req, "new.html", {"lines": LINES, "audiences": AUDIENCES, "trims": TRIMS})

    def enqueue_spec(spec: dict[str, Any]) -> int:
        q = queue()
        try:
            return q.add(
                "build_book",
                {"spec_yaml": yaml.safe_dump(spec, sort_keys=False)},
                spec["book"]["title"],
            )
        finally:
            q.close()

    @app.post("/new")
    async def new_book(req: Request, u: str = Depends(user)) -> Response:
        form = {k: str(v) for k, v in (await req.form()).items()}
        try:
            if form.get("spec_yaml", "").strip():
                spec = yaml.safe_load(form["spec_yaml"])
                from forge.core.book import BookSpec

                BookSpec.model_validate(spec)
            else:
                spec = spec_from_form(form)
        except (ValueError, KeyError, yaml.YAMLError) as exc:
            return page(
                req,
                "new.html",
                {
                    "lines": LINES,
                    "audiences": AUDIENCES,
                    "trims": TRIMS,
                    "error": str(exc)[:300],
                    "form": form,
                },
                422,
            )
        enqueue_spec(spec)
        return RedirectResponse("/", 303)

    @app.post("/new/csv")
    async def new_csv(req: Request, file: UploadFile, u: str = Depends(user)) -> Response:
        text = (await file.read()).decode("utf-8-sig")
        errors, n = [], 0
        for i, row in enumerate(csv.DictReader(io.StringIO(text)), 2):
            try:
                enqueue_spec(spec_from_form({k.strip(): (v or "").strip() for k, v in row.items()}))
                n += 1
            except (ValueError, KeyError) as exc:
                errors.append(f"dòng {i}: {exc}")
        if errors:
            return page(
                req,
                "new.html",
                {
                    "lines": LINES,
                    "audiences": AUDIENCES,
                    "trims": TRIMS,
                    "error": f"{n} sách vào hàng đợi; lỗi: " + "; ".join(errors[:10]),
                },
                422,
            )
        return RedirectResponse("/", 303)

    # ------------------------------------------------------------------ book page
    @app.get("/books/{book_id}", response_class=HTMLResponse)
    def book(req: Request, book_id: str, u: str = Depends(user)) -> HTMLResponse:
        from forge.qa.report import report_valid
        from forge.qa.state import StateStore

        d = book_dir(book_id)
        man = json.loads((d / "manifest.json").read_text())
        with StateStore(st.db_path) as store:
            state = store.current(book_id) or "DRAFT"
            history = store.history(book_id)
        files = sorted(
            str(p.relative_to(d))
            for p in d.rglob("*")
            if p.is_file()
            and p.suffix in (".pdf", ".json", ".yaml", ".csv", ".html", ".png")
            and "build" not in p.relative_to(d).parts
            and "thumbs" not in p.parts
        )
        return page(
            req,
            "book.html",
            {
                "book_id": book_id,
                "title": man["spec"]["book"]["title"],
                "state": state,
                "history": history,
                "files": files,
                "qa_valid": report_valid(d),
                "has_report": (d / "qa" / "qa_report.html").is_file(),
                "msg": req.query_params.get("msg", ""),
            },
        )

    @app.get("/books/{book_id}/files/{path:path}")
    def book_file(book_id: str, path: str, u: str = Depends(user)) -> FileResponse:
        d = book_dir(book_id)
        f = (d / path).resolve()
        if d not in f.parents or not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, filename=f.name if f.suffix != ".html" else None)

    @app.post("/books/{book_id}/review")
    def review(
        book_id: str, action: str = Form(""), note: str = Form(""), u: str = Depends(user)
    ) -> Response:
        from urllib.parse import quote

        from forge.book.review import ReviewError, review_book, vault_on_approved

        d = book_dir(book_id)
        try:
            msg = review_book(d, action == "approve", note, "owner(web)", st)
            if action == "approve":
                msg += " · " + vault_on_approved(d, st)
        except ReviewError as exc:
            msg = f"Lỗi: {exc}"
        return RedirectResponse(f"/books/{book_id}?msg={quote(msg)}", 303)

    @app.post("/books/{book_id}/qa")
    def rerun_qa(book_id: str, u: str = Depends(user)) -> Response:
        d = book_dir(book_id)
        q = queue()
        try:
            q.add("qa_run", {"out_dir": str(d)}, f"QA {book_id}")
        finally:
            q.close()
        return RedirectResponse("/", 303)

    # ------------------------------------------------------------------ settings
    def settings_ctx() -> dict[str, Any]:
        from dotenv import dotenv_values

        from forge.ai.ledger import Ledger
        from forge.ai.routing import Routing
        from forge.secrets import SecretStore

        routing = Routing.load(st.config_dir, st.env)
        env_vals = dotenv_values(st.config_file) if st.config_file.is_file() else {}
        led = Ledger(st.db_path)
        try:
            p = led.periods()
            spend = {"day": led.spent(p["day"]), "month": led.spent(p["month"])}
            usage = led.report("provider", 30)
        finally:
            led.close()
        return {
            "secrets": {
                k: v for k, v in SecretStore(st.config_dir).masked().items() if k in SECRET_KEYS
            },
            "routes": [routing.route(t) for t in routing.tasks()],
            "budget": routing.budget(),
            "spend": spend,
            "usage": usage,
            "env_keys": ENV_KEYS,
            "env_vals": env_vals,
            "config_file": str(st.config_file),
            "brand": _brand_raw(st),
        }

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(req: Request, u: str = Depends(user)) -> HTMLResponse:
        return page(req, "settings.html", {**settings_ctx(), "msg": req.query_params.get("msg")})

    @app.post("/settings/secret")
    def set_secret(
        name: str = Form(...), value: str = Form(""), u: str = Depends(user)
    ) -> Response:
        from forge.secrets import SecretStore

        if name not in SECRET_KEYS:
            raise HTTPException(400, "unknown secret")
        SecretStore(st.config_dir).set(name, value)
        return RedirectResponse("/settings?msg=Đã+lưu+(mã+hoá).+Khởi+động+lại+worker.", 303)

    @app.get("/settings/ai/test/{provider}", response_class=HTMLResponse)
    def ai_test(provider: str, u: str = Depends(user)) -> HTMLResponse:
        from forge.ai.providers import build_provider

        cur = get_settings()  # re-read: a key may have just been saved
        try:
            p = build_provider(provider, cur.secret)
            if p is None:
                return HTMLResponse("<span class='warn'>chưa có key</span>")
            n = len(p.list_models())
            return HTMLResponse(f"<span class='ok'>OK: {n} model</span>")
        except Exception as exc:
            return HTMLResponse(f"<span class='err'>Lỗi: {str(exc)[:150]}</span>")

    @app.get("/settings/ai/models/{provider}")
    def ai_models(provider: str, u: str = Depends(user)) -> JSONResponse:
        from forge.ai.providers import build_provider

        p = build_provider(provider, get_settings().secret)
        if p is None:
            return JSONResponse({"models": [], "error": "no key"})
        try:
            return JSONResponse({"models": p.list_models()})
        except Exception as exc:
            return JSONResponse({"models": [], "error": str(exc)[:200]})

    @app.post("/settings/ai/routing")
    async def save_routing(req: Request, u: str = Depends(user)) -> Response:
        from forge.ai.routing import Routing

        form = await req.form()
        routing = Routing.load(st.config_dir, st.env)
        data = json.loads(json.dumps(routing.data))
        for t in routing.tasks():
            prov, model = str(form.get(f"{t}.provider", "")), str(form.get(f"{t}.model", ""))
            if prov and model:
                data["tasks"][t] = {
                    **(data["tasks"].get(t) or {}),
                    "provider": prov,
                    "model": model,
                }
        env_budget = (data.get("budget_by_env") or {}).get(st.env)
        for k in ("daily_usd", "monthly_usd", "per_book_usd"):
            v = str(form.get(f"budget.{k}", "")).strip()
            if v:
                target = env_budget if env_budget is not None else data.setdefault("budget", {})
                target[k] = float(v)
        st.config_dir.mkdir(parents=True, exist_ok=True)
        (st.config_dir / "ai_routing.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
        return RedirectResponse("/settings?msg=Đã+lưu+định+tuyến+AI", 303)

    @app.post("/settings/env")
    async def save_env(req: Request, u: str = Depends(user)) -> Response:
        from dotenv import set_key

        form = await req.form()
        st.config_file.parent.mkdir(parents=True, exist_ok=True)
        st.config_file.touch(mode=0o600, exist_ok=True)
        for k in ENV_KEYS:
            if k in form:
                set_key(str(st.config_file), k, str(form[k]).strip(), quote_mode="never")
        return RedirectResponse("/settings?msg=Đã+lưu.+Chạy+`forge+restart`+để+áp+dụng.", 303)

    @app.post("/settings/brand")
    async def save_brand(req: Request, u: str = Depends(user)) -> Response:
        form = await req.form()
        raw = _brand_raw(st)
        for k in ("brand_name", "website", "primary_color", "license_line"):
            if form.get(k):
                raw[k] = str(form[k]).strip()
        raw["placeholder"] = False
        st.config_dir.mkdir(parents=True, exist_ok=True)
        (st.config_dir / "brand.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
        return RedirectResponse("/settings?msg=Đã+lưu+brand", 303)

    # ------------------------------------------------------------------ JSON API
    @app.get("/api/jobs")
    def api_jobs(u: str = Depends(user)) -> list[dict[str, Any]]:
        q = queue()
        try:
            return [j.__dict__ for j in q.recent(100)]
        finally:
            q.close()

    return app


def _brand_raw(st: Settings) -> dict[str, Any]:
    from forge.editions.brand import brand_path

    return dict(yaml.safe_load(brand_path().read_text(encoding="utf-8")))


def app_factory() -> FastAPI:  # uvicorn forge.web.app:app_factory --factory
    return create_app()
