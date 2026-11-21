"""Encrypted secret store (Fernet, `cryptography`): API keys entered in the web UI.

File: <config_dir>/secrets.enc, key: <config_dir>/secret.key (both mode 600, owned by user `forge`).
Environment variables (forge.env) win over the store, so a key can always be overridden."""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

KNOWN = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "HALOSPARK_AI_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "HUB_TOKEN",
    "VAULT_ADMIN_TOKEN",
    "VAULT_ANSWER_KEY",
    "VAULT_STAGING_ADMIN_TOKEN",
    "VAULT_STAGING_ANSWER_KEY",
    "FORGE_WEB_PASSWORD_HASH",
)


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(path, 0o600)


class SecretStore:
    def __init__(self, config_dir: Path) -> None:
        self.dir = config_dir
        self.key_file = config_dir / "secret.key"
        self.file = config_dir / "secrets.enc"

    def _fernet(self, create: bool) -> Fernet | None:
        if not self.key_file.is_file():
            if not create:
                return None
            _write_private(self.key_file, Fernet.generate_key())
        return Fernet(self.key_file.read_bytes().strip())

    def _load(self) -> dict[str, str]:
        f = self._fernet(create=False)
        if f is None or not self.file.is_file():
            return {}
        try:
            return dict(json.loads(f.decrypt(self.file.read_bytes())))
        except (InvalidToken, ValueError) as exc:
            raise RuntimeError(f"{self.file}: cannot decrypt (wrong secret.key?)") from exc

    def get(self, name: str) -> str:
        return os.environ.get(name, "").strip() or self._load().get(name, "")

    def set(self, name: str, value: str) -> None:
        data = self._load()
        if value:
            data[name] = value.strip()
        else:
            data.pop(name, None)
        f = self._fernet(create=True)
        assert f is not None
        _write_private(self.file, f.encrypt(json.dumps(data).encode()))

    def masked(self) -> dict[str, dict[str, str]]:
        stored = self._load()
        out = {}
        for k in KNOWN:
            src = "env" if os.environ.get(k, "").strip() else ("store" if k in stored else "")
            out[k] = {"source": src, "masked": mask(self.get(k))}
        return out
