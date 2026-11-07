"""Runtime settings from environment / `.env` (never hard-code machine paths)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def _path(value: str | None, default: str) -> Path:
    p = Path(value or default).expanduser()
    return p if p.is_absolute() else Path.cwd() / p


@dataclass(frozen=True)
class Settings:
    output_dir: Path
    db_path: Path
    typst_bin: str | None
    anthropic_api_key: str | None
    openai_api_key: str | None
    llm_provider: str
    vault_url: str = ""
    vault_token: str = ""
    vault_answer_key: str = ""
    vault_domain: str = ""


def get_settings(env_file: str | Path | None = None) -> Settings:
    """Read settings. `.env` in the current directory is loaded (without overriding env)."""
    load_dotenv(env_file or Path.cwd() / ".env", override=False)
    return Settings(
        output_dir=_path(os.environ.get("FORGE_OUTPUT_DIR"), "output"),
        db_path=_path(os.environ.get("FORGE_DB_PATH"), "data/forge.db"),
        typst_bin=os.environ.get("FORGE_TYPST_BIN") or None,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        llm_provider=os.environ.get("FORGE_LLM_PROVIDER") or "anthropic",
        vault_url=os.environ.get("VAULT_URL", "").strip(),
        vault_token=os.environ.get("VAULT_ADMIN_TOKEN", "").strip(),
        vault_answer_key=os.environ.get("VAULT_ANSWER_KEY", "").strip(),
        vault_domain=os.environ.get("VAULT_DOMAIN", "").strip(),
    )
