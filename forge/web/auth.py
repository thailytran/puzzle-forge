"""Single owner login: scrypt password hash (secret store), signed session cookie, lock-out."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

PURPOSE = "forge-web"


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, s, d = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.scrypt(pw.encode(), salt=base64.b64decode(s), n=2**14, r=8, p=1)
    return hmac.compare_digest(dk, base64.b64decode(d))


def session_key(config_dir: Path) -> bytes:
    p = config_dir / "web_session.key"
    if not p.is_file():
        from forge.secrets import _write_private

        _write_private(p, secrets.token_bytes(32))
    return p.read_bytes()


def make_cookie(key: bytes, user: str, ttl_s: int = 12 * 3600) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps({"u": user, "e": int(time.time()) + ttl_s, "p": PURPOSE}).encode()
    ).decode()
    mac = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def read_cookie(key: bytes, value: str) -> str | None:
    try:
        body, mac = value.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(mac, hmac.new(key, body.encode(), hashlib.sha256).hexdigest()):
        return None
    data = json.loads(base64.urlsafe_b64decode(body))
    if data.get("p") != PURPOSE or data.get("e", 0) < time.time():
        return None
    return str(data["u"])
