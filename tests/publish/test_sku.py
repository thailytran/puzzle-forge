from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from forge.adapters.sku_dev import DevSkuProvider
from forge.adapters.sku_hub import HubSkuProvider
from forge.ports import SkuError, SkuPort, SkuRequest
from forge.publish.sku import SKU_RE, SkuConfig, assign_sku

REQ = SkuRequest(
    book_id="b1",
    title="Ocean Word Search",
    audience_code="KID4",
    brand="HSP",
    line="PZL",
    format="PBK",
)


def test_config_codes() -> None:
    cfg = SkuConfig.load()
    assert cfg.code_for("kids_6_8") == "KID4"
    assert cfg.code_for("kids_9_12") == "KID9"
    assert cfg.code_for("adult") == "ADULT"
    assert cfg.aliases["KID"] == "KID4"
    with pytest.raises(SkuError):
        cfg.code_for("aliens")


def test_dev_provider_prefix_and_counter(tmp_path: Path) -> None:
    p = DevSkuProvider(tmp_path / "d.db")
    assert isinstance(p, SkuPort)
    a, b = p.assign(REQ).sku, p.assign(REQ).sku
    assert a == "DEV-HSP-KID4-PZL-PBK-0001-SGL"
    assert b.endswith("-0002-SGL")
    assert SKU_RE.match(a)


class _Hub(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Hub.seen.append(
            {"path": self.path, "token": self.headers.get("X-Hub-Token"), "body": body}
        )
        if self.headers.get("X-Hub-Token") != "secret":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error": "bad token"}')
            return
        out = json.dumps({"sku": f"HSP-{body['audience']}-PZL-PBK-0042-SGL", "status": "idea"})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out.encode())

    def log_message(self, *a: object) -> None:
        pass


@pytest.fixture
def hub() -> str:
    srv = HTTPServer(("127.0.0.1", 0), _Hub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/hooks/product-hub"
    srv.shutdown()


def test_hub_provider_contract(hub: str) -> None:
    _Hub.seen.clear()
    res = HubSkuProvider(hub, "secret").assign(REQ)
    assert res.sku == "HSP-KID4-PZL-PBK-0042-SGL"
    call = _Hub.seen[0]
    assert call["path"] == "/hooks/product-hub/api/products"
    assert call["token"] == "secret"
    assert call["body"]["audience"] == "KID4" and call["body"]["line"] == "PZL"
    assert call["body"]["topic"] == "Ocean Word Search" and call["body"]["source"] == "puzzle-forge"


def test_hub_bad_token(hub: str) -> None:
    with pytest.raises(SkuError, match="401"):
        HubSkuProvider(hub, "wrong").assign(REQ)


def test_hub_needs_config() -> None:
    with pytest.raises(SkuError):
        HubSkuProvider("", "")


def test_hub_unreachable() -> None:
    with pytest.raises(SkuError, match="unreachable"):
        HubSkuProvider("http://127.0.0.1:9", "x").assign(REQ)


def test_assign_is_idempotent(tmp_path: Path) -> None:
    out = tmp_path / "book"
    out.mkdir()
    spec = {"book": {"title": "T", "audience": "kids_9_12"}}
    (out / "manifest.json").write_text(json.dumps({"book_id": "b9", "spec": spec}))
    p = DevSkuProvider(tmp_path / "d.db")
    first = assign_sku(out, p)
    assert first["sku"].startswith("DEV-HSP-KID9-PZL-PBK-")
    assert assign_sku(out, p) == first
