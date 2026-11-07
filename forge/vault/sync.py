"""Registration of APPROVED books on the Case Vault site, through a SQLite outbox with retry.

`enqueue_book` builds the payload (hashes only, never plaintext answers or Book Codes) and stores
it; `sync` sends every due item; offline -> the item stays queued with exponential back-off."""

from __future__ import annotations

import base64
import json
import sqlite3
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forge.vault.answers import answer_hash, code_hash
from forge.vault.bookcode import canonical
from forge.vault.codes import read_batches
from forge.vault.spec import load_vault_spec

TIMEOUT_S = 30
MAX_ATTEMPTS = 30

Sender = Callable[[dict[str, Any]], dict[str, Any]]


class VaultError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def http_sender(base_url: str, token: str) -> Sender:
    """POST {VAULT_URL}/api/admin/books with Authorization: Bearer <VAULT_ADMIN_TOKEN>."""
    if not base_url or not token:
        raise VaultError("VAULT_URL and VAULT_ADMIN_TOKEN must be set in .env")

    def send(payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            base_url.rstrip("/") + "/api/admin/books",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return dict(json.loads(resp.read().decode() or "{}"))
        except urllib.error.HTTPError as exc:
            raise VaultError(
                f"HTTP {exc.code} {exc.read().decode(errors='replace')[:200]}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VaultError(f"unreachable: {exc}") from exc

    return send


def _cover_png(out_dir: Path) -> str:
    pdf = out_dir / "cover.pdf"
    if not pdf.is_file():
        pdf = out_dir / "interior.pdf"
    if not pdf.is_file():
        return ""
    import io

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    try:
        img = doc[0].render(scale=60 / 72).to_pil()
    finally:
        doc.close()
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def build_payload(out_dir: Path, key: str) -> dict[str, Any]:
    if not key:
        raise VaultError("VAULT_ANSWER_KEY must be set in .env (same value as on the server)")
    spec = load_vault_spec(out_dir)
    if spec is None:
        raise VaultError(f"{out_dir}/vault.yaml missing (classic book or run `forge vault init`)")
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    bid = str(manifest["book_id"])
    sku_file = out_dir / "sku.json"
    sku = json.loads(sku_file.read_text())["sku"] if sku_file.is_file() else ""
    eds = sorted(p.name for p in (out_dir / "editions").glob("*") if p.is_dir())
    editions = ["kdp", *eds]
    answers = {
        kind: sorted({answer_hash(key, bid, kind, str(v)) for v in getattr(spec, kind)})
        for kind in spec.kinds()
    }
    batches = [
        {
            "batch_id": b["batch_id"],
            "channel": b["channel"],
            "code_hashes": [code_hash(key, bid, canonical(str(c))) for c in b["codes"]],  # type: ignore[attr-defined]
        }
        for b in read_batches(out_dir)
    ]
    return {
        "book_id": bid,
        "sku": sku,
        "title": manifest["spec"]["book"]["title"],
        "editions": editions,
        "answer_type": spec.answer_type,
        "answers": answers,
        "book_code_batches": batches,
        "etsy_listing_ids": [str(x) for x in spec.etsy_listing_ids],
        "shopify_product_ids": spec.shopify_product_ids,
        "cover_png_b64": _cover_png(out_dir),
    }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT NOT NULL, payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
    next_at TEXT NOT NULL, last_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
    sent_at TEXT
);
"""


@dataclass
class OutboxItem:
    id: int
    book_id: str
    status: str
    attempts: int
    next_at: str
    last_error: str
    created_at: str
    sent_at: str | None


class VaultOutbox:
    def __init__(self, db_path: str | Path) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(db_path)
        self._c.executescript(_SCHEMA)

    def close(self) -> None:
        self._c.close()

    def enqueue(self, book_id: str, payload: dict[str, Any]) -> int:
        """One queued item per book: a newer payload replaces a queued one."""
        now = _now().isoformat()
        with self._c:
            self._c.execute(
                "UPDATE vault_outbox SET status='superseded' WHERE book_id=? AND status='queued'",
                (book_id,),
            )
            cur = self._c.execute(
                "INSERT INTO vault_outbox(book_id, payload, next_at, created_at) VALUES (?,?,?,?)",
                (book_id, json.dumps(payload), now, now),
            )
        return int(cur.lastrowid or 0)

    def items(self, book_id: str | None = None) -> list[OutboxItem]:
        q = (
            "SELECT id, book_id, status, attempts, next_at, last_error, created_at, sent_at "
            "FROM vault_outbox WHERE status != 'superseded'"
        )
        args: tuple[Any, ...] = ()
        if book_id:
            q += " AND book_id=?"
            args = (book_id,)
        return [OutboxItem(*r) for r in self._c.execute(q + " ORDER BY id", args)]

    def sync(self, send: Sender, force: bool = False) -> dict[str, int]:
        now = _now()
        rows = self._c.execute(
            "SELECT id, payload, attempts, next_at FROM vault_outbox WHERE status='queued' "
            "ORDER BY id"
        ).fetchall()
        sent = failed = 0
        for rid, payload, attempts, next_at in rows:
            if not force and datetime.fromisoformat(next_at) > now:
                continue
            try:
                send(json.loads(payload))
            except Exception as exc:
                n = attempts + 1
                with self._c:
                    self._c.execute(
                        "UPDATE vault_outbox SET attempts=?, last_error=?, next_at=?, status=? "
                        "WHERE id=?",
                        (
                            n,
                            str(exc)[:500],
                            (now + timedelta(minutes=min(2**n, 720))).isoformat(),
                            "dead" if n >= MAX_ATTEMPTS else "queued",
                            rid,
                        ),
                    )
                failed += 1
                continue
            with self._c:
                self._c.execute(
                    "UPDATE vault_outbox SET status='sent', sent_at=?, last_error='' WHERE id=?",
                    (now.isoformat(), rid),
                )
            sent += 1
        return {"sent": sent, "failed": failed}
