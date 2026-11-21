import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from forge.vault import answers as fa
from forge.vault import bookcode as fb
from forge.vault.codes import code_pages_pdf, make_batch, read_batches
from forge.vault.qr import qr_svg, solve_url
from forge.vault.spec import VaultSpec, init_vault_spec, load_vault_spec
from forge.vault.sync import VaultError, VaultOutbox, build_payload

KEY = "k-test"
VECTORS = [
    ("culprit_name", " Captain  Réed! "),
    ("culprit_name", "ELIAS-REED"),
    ("culprit_name", "Zoë O'Hara"),
    ("unlock_code", "04 - 72"),
    ("unlock_code", "K7"),
]


def test_same_algorithms_as_the_website():
    from casevault import answers as ca
    from casevault import bookcode as cb

    for kind, text in VECTORS:
        assert fa.normalize(kind, text) == ca.normalize(kind, text)
        assert fa.answer_hash(KEY, "b", kind, text) == ca.answer_hash(KEY, "b", kind, text)
    code = fb.new_code()
    assert cb.is_valid(code) and fb.check_char(code[:-1]) == cb.check_char(code[:-1])
    assert fa.code_hash(KEY, "b", code) == ca.code_hash(KEY, "b", code)
    assert fb.ALPHABET == cb.ALPHABET


def book(tmp_path: Path, answers: dict | None = None) -> Path:
    out = tmp_path / "bk-1"
    out.mkdir()
    manifest = {
        "book_id": "bk-1",
        "spec": {"book": {"title": "The Lighthouse Case", "trim": "6x9"}},
    }
    (out / "manifest.json").write_text(json.dumps(manifest))
    (out / "sku.json").write_text(json.dumps({"sku": "HSP-ADULT-PZL-PBK-0001-SGL"}))
    spec = answers or {
        "answer_type": "culprit_name",
        "culprit_name": ["Captain Reed", "Reed"],
        "etsy_listing_ids": [123],
    }
    (out / "vault.yaml").write_text(yaml.safe_dump(spec))
    return out


def test_spec_validation(tmp_path):
    with pytest.raises(ValueError, match="unlock_code needs"):
        VaultSpec(answer_type="both", culprit_name=["Reed"])
    p = init_vault_spec(tmp_path)
    assert "answer_type" in p.read_text()
    with pytest.raises(ValueError):
        load_vault_spec(tmp_path)  # template has no answers yet


def test_payload_has_hashes_only(tmp_path):
    out = book(tmp_path)
    make_batch(out, 3, "print", "b1")
    p = build_payload(out, KEY)
    blob = json.dumps(p)
    assert "Reed" not in blob and "Captain" not in blob
    assert p["answers"]["culprit_name"] == sorted(
        {fa.answer_hash(KEY, "bk-1", "culprit_name", v) for v in ("Captain Reed", "Reed")}
    )
    codes = read_batches(out)[0]["codes"]
    assert all(c not in blob for c in codes)
    assert len(p["book_code_batches"][0]["code_hashes"]) == 3
    assert p["sku"] == "HSP-ADULT-PZL-PBK-0001-SGL" and p["etsy_listing_ids"] == ["123"]
    with pytest.raises(VaultError, match="VAULT_ANSWER_KEY"):
        build_payload(out, "")


def test_outbox_retries_then_sends(tmp_path):
    box = VaultOutbox(tmp_path / "f.db")
    box.enqueue("bk-1", {"v": 1})
    box.enqueue("bk-1", {"v": 2})  # replaces the queued one

    def down(p):
        raise VaultError("unreachable")

    assert box.sync(down) == {"sent": 0, "failed": 1}
    assert box.sync(down) == {"sent": 0, "failed": 0}  # back-off: not due yet
    got = []
    assert box.sync(lambda p: got.append(p) or {}, force=True) == {"sent": 1, "failed": 0}
    assert got == [{"v": 2}]
    (item,) = box.items("bk-1")
    assert item.status == "sent" and item.attempts == 1


def test_registered_book_is_solvable_on_the_website(tmp_path):
    """forge payload -> casevault admin API -> reader solves with a printed Book Code."""
    from casevault import db as T
    from casevault.config import Settings, load_rules
    from casevault.providers import OrderLookup, Providers
    from casevault.web import create_app
    from fastapi.testclient import TestClient

    class Null:
        def __getattr__(self, name):
            return lambda *a, **k: None

    class NoEtsy:
        def lookup(self, order_id):
            return OrderLookup("unavailable")

    class Ok:
        def verify(self, token, ip):
            return True

    s = Settings(
        database_url=f"sqlite:///{tmp_path}/cv.db",
        public_url="https://cv.test",
        admin_api_token="tok",
        answer_key=KEY,
        secure_cookies=False,
        rules=load_rules(),
    )
    shop = Null()
    app = create_app(
        s, Providers(NoEtsy(), shop, Null(), Null(), Ok()), T.make_engine(s.database_url)
    )
    client = TestClient(app)
    out = book(tmp_path)
    make_batch(out, 2, "print", "b1")
    code = read_batches(out)[0]["codes"][0]

    def send(payload):
        r = client.post("/api/admin/books", json=payload, headers={"Authorization": "Bearer tok"})
        if r.status_code != 200:
            raise VaultError(r.text)
        return r.json()

    box = VaultOutbox(tmp_path / "f.db")
    box.enqueue("bk-1", build_payload(out, KEY))
    assert box.sync(send)["sent"] == 1
    r = client.post(
        "/solve/bk-1",
        data={
            "culprit_name": "reed",
            "purchase_place": "in_person",
            "proof": fb.pretty(code),
            "email": "a@example.com",
            "country": "US",
            "newsletter": "1",
            "terms": "1",
        },
    )
    assert "Case solved" in r.text


def test_cli_init_and_status(tmp_path, monkeypatch):
    from forge.cli import _vault_on_approved, app

    monkeypatch.setenv("FORGE_DB_PATH", str(tmp_path / "f.db"))
    monkeypatch.setenv("VAULT_ANSWER_KEY", KEY)
    monkeypatch.setenv("VAULT_URL", "")
    out = book(tmp_path)
    _vault_on_approved(out)
    r = CliRunner().invoke(app, ["vault", "status"])
    assert r.exit_code == 0 and "bk-1" in r.stdout and "queued" in r.stdout
    r = CliRunner().invoke(app, ["vault", "sync"])
    assert r.exit_code == 1  # VAULT_URL missing
    r = CliRunner().invoke(app, ["vault", "init", str(tmp_path)])
    assert r.exit_code == 0 and (tmp_path / "vault.yaml").exists()


def test_qr():
    assert solve_url("cv.example.com", "bk") == "https://cv.example.com/solve/bk"
    assert solve_url("https://x.io/", "bk", "ABC") == "https://x.io/solve/bk?code=ABC"
    assert qr_svg("https://x.io").startswith("<svg")


@pytest.mark.typst
def test_code_pages_pdf(tmp_path):
    from pypdf import PdfReader

    out = book(tmp_path)
    csv_path = make_batch(out, 2, "print", "b1")
    pdf = code_pages_pdf(out, csv_path, "cv.example.com")
    reader = PdfReader(pdf)
    assert len(reader.pages) == 2
    text = reader.pages[0].extract_text()
    assert "cv.example.com/solve/bk-1" in text
    codes = {r for r in read_batches(out)[0]["codes"]}
    assert any(fb.pretty(c) in "".join(p.extract_text() for p in reader.pages) for c in codes)
