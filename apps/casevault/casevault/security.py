"""Password hashing (scrypt), TOTP 2FA (RFC 6238) and signed tokens — standard library only."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from typing import Any
from urllib.parse import quote


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1)
    return hmac.compare_digest(dk, base64.b64decode(dk_b64))


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = int((time.time() if at is None else at) // step)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off : off + 4])[0] & 0x7FFFFFFF) % 10**digits
    return str(code).zfill(digits)


def check_totp(secret: str, code: str, at: float | None = None) -> bool:
    t = time.time() if at is None else at
    code = code.strip().replace(" ", "")
    return any(hmac.compare_digest(totp(secret, t + d * 30), code) for d in (-1, 0, 1))


def otpauth_uri(secret: str, username: str, issuer: str) -> str:
    return (
        f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}&issuer={quote(issuer)}"
    )


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(key: str, data: dict[str, Any], ttl_s: int, purpose: str) -> str:
    body = _b64(json.dumps({**data, "_p": purpose, "_e": int(time.time()) + ttl_s}).encode())
    mac = hmac.new(key.encode(), body.encode(), hashlib.sha256).digest()
    return body + "." + _b64(mac)


def unsign(key: str, token: str, purpose: str) -> dict[str, Any] | None:
    try:
        body, mac = token.split(".")
        good = hmac.new(key.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(good, _unb64(mac)):
            return None
        data = dict(json.loads(_unb64(body)))
    except (ValueError, json.JSONDecodeError):
        return None
    if data.pop("_p", None) != purpose or data.pop("_e", 0) < time.time():
        return None
    return data
