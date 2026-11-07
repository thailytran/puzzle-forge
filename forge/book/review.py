"""Manual review (CLI `forge review` and the web UI share this)."""

from __future__ import annotations

import json
from pathlib import Path

from forge.config import Settings


class ReviewError(Exception):
    pass


def review_book(out_dir: Path, approve: bool, note: str, by: str, st: Settings) -> str:
    """MANUAL_REVIEW -> APPROVED | REJECTED (-> DRAFT); APPROVED queues the Case Vault entry."""
    from forge.qa.gate import sync_state
    from forge.qa.state import IllegalTransition, StateStore

    book_id = json.loads((out_dir / "manifest.json").read_text())["book_id"]
    with StateStore(st.db_path) as store:
        state = sync_state(store, book_id, out_dir)
        if state != "MANUAL_REVIEW":
            raise ReviewError(
                f"{book_id} is {state}; only MANUAL_REVIEW books can be reviewed "
                "(QA_PASSED -> SKU -> metadata first, see docs/QA_SPEC.md)"
            )
        try:
            store.transition(book_id, "APPROVED" if approve else "REJECTED", actor=by, note=note)
            if not approve:
                store.transition(book_id, "DRAFT", actor=by, note="rejected: " + note)
        except IllegalTransition as exc:
            raise ReviewError(str(exc)) from exc
    return "APPROVED" if approve else "REJECTED -> DRAFT"


def vault_on_approved(out_dir: Path, st: Settings) -> str:
    """Queue (and try to send) the Case Vault registration; returns a one-line status."""
    from forge.vault.spec import load_vault_spec
    from forge.vault.sync import VaultError, VaultOutbox, build_payload, sender_for

    if load_vault_spec(out_dir) is None:
        return "Case Vault: no vault.yaml (classic book) - not registered"
    try:
        payload = build_payload(out_dir, st.vault_answer_key)
    except VaultError as exc:
        return f"Case Vault: {exc}"
    box = VaultOutbox(st.db_path)
    try:
        box.enqueue(payload["book_id"], payload)
        if st.vault_url and (st.vault_token or st.vault_url == "mock"):
            res = box.sync(sender_for(st.vault_url, st.vault_token, st.data_dir))
            return f"Case Vault: sent {res['sent']}, queued for retry {res['failed']}"
        return "Case Vault: queued (set VAULT_URL + VAULT_ADMIN_TOKEN, then `forge vault sync`)"
    finally:
        box.close()
