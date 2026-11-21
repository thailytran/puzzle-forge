"""`forge smoke-run`: end-to-end check of an install (FORGE_ENV=test).

1. word search sample -> QA_PASSED
2. escape stand-in (mixed puzzles + vault.yaml + case_vault last page) -> QA_PASSED -> DEV SKU ->
   MANUAL_REVIEW -> APPROVED -> Case Vault staging (or mock) registration with one Book Code
3. redeem on staging through the public form (Turnstile test token) -> "Case solved"
   (the Klaviyo "Case Solved" e-mail goes to --email if the staging site has Klaviyo test keys)
The real escape pipeline arrives with P3; this book only exercises the packaging."""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from forge.config import Settings

TURNSTILE_TEST_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"  # Cloudflare's documented test response
Poster = Callable[[str, dict[str, str]], str]


class SmokeError(Exception):
    pass


def _post(url: str, form: dict[str, str]) -> str:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"User-Agent": "puzzle-forge-smoke"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return str(resp.read().decode("utf-8", "replace"))


def _build(st: Settings, spec: dict[str, Any], vault: dict[str, Any] | None = None) -> Path:
    from forge.book.builder import build_book
    from forge.core.book import BookSpec
    from forge.qa.fixer import regenerate_failing
    from forge.qa.gate import run_gate

    out = build_book(BookSpec.model_validate(spec), st.output_dir, st.db_path)
    if vault:
        (out / "vault.yaml").write_text(yaml.safe_dump(vault))
    report = run_gate(out, st.db_path, fixer=regenerate_failing)
    if report.result != "PASSED":
        bad = [c.id for c in report.checks if c.status == "fail" and not c.waived]
        raise SmokeError(f"{out.name}: QA {report.result} {bad}")
    return out


def _approve(st: Settings, out: Path) -> None:
    import json

    from forge.book.review import review_book
    from forge.publish.sku import assign_sku, provider_from_env
    from forge.qa.state import StateStore

    book_id = json.loads((out / "manifest.json").read_text())["book_id"]
    data = assign_sku(out, provider_from_env(st.db_path))
    with StateStore(st.db_path) as store:
        store.transition(book_id, "SKU_ASSIGNED", actor="smoke", note=data["sku"])
        store.transition(book_id, "METADATA_READY", actor="smoke", note="smoke test (no book_card)")
        store.transition(book_id, "MANUAL_REVIEW", actor="smoke")
    review_book(out, True, "smoke test", "smoke", st)


def run_smoke(
    st: Settings,
    email: str = "smoke-test@example.com",
    post: Poster = _post,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    if st.env != "test":
        raise SmokeError(
            "run the smoke test with FORGE_ENV=test (it creates DEV SKUs and "
            "registers on Case Vault staging)"
        )
    from forge.book.review import vault_on_approved
    from forge.vault.codes import make_batch, read_batches
    from forge.vault.qr import solve_url

    seed = int(time.time()) % 90000 + 1000
    res: dict[str, Any] = {}
    log("1/3 word search sample")
    ws = _build(
        st,
        {
            "book": {
                "title": f"Smoke Word Search {seed}",
                "audience": "kids_6_8",
                "trim": "8.5x11",
                "content_pages": 6,
                "seed": seed,
            },
            "puzzles": {"mode": "progressive", "types": [{"type": "wordsearch"}]},
        },
    )
    res["wordsearch"] = ws.name
    log(f"    QA_PASSED {ws.name}")

    log("2/3 escape sample -> approve -> Case Vault")
    if not st.vault_domain:
        if st.vault_url not in ("", "mock"):
            raise SmokeError("set VAULT_STAGING_DOMAIN (printed on the last page)")
        import os

        os.environ["VAULT_STAGING_DOMAIN"] = "casevault.test"  # mock: any domain will do
    esc = _build(
        st,
        {
            "book": {
                "title": f"Smoke Case {seed}",
                "audience": "adult",
                "trim": "8.5x11",
                "content_pages": 6,
                "seed": seed,
            },
            "puzzles": {
                "mode": "mixed",
                "types": [{"type": "sudoku"}, {"type": "cryptogram"}, {"type": "maze"}],
            },
            "back_matter": ["solutions", "case_vault"],
        },
        vault={"answer_type": "culprit_name", "culprit_name": ["Captain Reed", "Reed"]},
    )
    make_batch(esc, 1, "print", f"smoke-{seed}")
    _approve(st, esc)
    msg = vault_on_approved(esc, st)
    log(f"    {msg}")
    res["escape"] = esc.name
    res["vault"] = msg
    if "sent 1" not in msg:
        raise SmokeError(f"Case Vault registration not sent: {msg}")

    log("3/3 redeem on staging")
    if st.vault_url == "mock":
        log("    VAULT_STAGING_URL=mock: payload written to data/vault_mock/, redeem skipped")
        res["redeem"] = "skipped (mock)"
        return res
    code = str(read_batches(esc)[0]["codes"][0])  # type: ignore[index]
    url = solve_url(st.vault_url, esc.name)
    html = post(
        url,
        {
            "culprit_name": "Reed",
            "purchase_place": "in_person",
            "proof": code,
            "email": email,
            "country": "US",
            "newsletter": "1",
            "terms": "1",
            "cf-turnstile-response": TURNSTILE_TEST_TOKEN,
        },
    )
    if "Case solved" not in html:
        raise SmokeError(f"redeem failed on {url}: {html[:300]}")
    res["redeem"] = f"Case solved ({email})"
    log(f"    Case solved - check the Klaviyo test list / inbox of {email}")
    return res
