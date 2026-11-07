"""Runtime settings (never hard-code machine paths).

Where configuration comes from (first match wins):
  1. process environment,
  2. env file: $FORGE_CONFIG, else /etc/puzzle-forge/forge.env (installed VM), else ./.env,
  3. the encrypted secret store <config_dir>/secrets.enc (API keys entered in the web UI).
FORGE_ENV = dev | test | prod changes defaults (docs/INSTALL_VM.md):
  test -> DevSkuProvider, Case Vault staging (or "mock"), low AI budget; prod -> Hub SKU.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_ENV_FILE = Path("/etc/puzzle-forge/forge.env")
ENVS = ("dev", "test", "prod")


def _path(value: str | None, default: Path) -> Path:
    p = Path(value).expanduser() if value else default
    return p if p.is_absolute() else Path.cwd() / p


def env_file() -> Path:
    if os.environ.get("FORGE_CONFIG"):
        return Path(os.environ["FORGE_CONFIG"])
    return SYSTEM_ENV_FILE if SYSTEM_ENV_FILE.is_file() else Path.cwd() / ".env"


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
    env: str = "dev"
    data_dir: Path = Path(".")
    config_dir: Path = Path(".")
    config_file: Path = Path(".env")
    sku_provider: str = "hub"
    gemini_api_key: str | None = None
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    web_host: str = "127.0.0.1"
    web_port: int = 8710
    backup_remote: str = ""  # rclone remote, e.g. gdrive:puzzle-forge-backups

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    def secret(self, name: str) -> str:
        from forge.secrets import SecretStore

        return SecretStore(self.config_dir).get(name)


def get_settings(env_path: str | Path | None = None) -> Settings:
    """Read settings; the env file is loaded without overriding the process environment."""
    cfg = Path(env_path) if env_path else env_file()
    load_dotenv(cfg, override=False)
    env = os.environ.get("FORGE_ENV", "dev").strip().lower() or "dev"
    if env not in ENVS:
        raise ValueError(f"FORGE_ENV must be one of {ENVS}, got {env!r}")
    data = _path(os.environ.get("FORGE_DATA_DIR"), Path.cwd())
    conf_dir = _path(
        os.environ.get("FORGE_CONFIG_DIR"),
        cfg.parent if cfg == SYSTEM_ENV_FILE else data / "data" / "config",
    )
    from forge.secrets import SecretStore

    store = SecretStore(conf_dir)

    def sec(name: str) -> str:
        try:
            return store.get(name)
        except RuntimeError:
            return os.environ.get(name, "").strip()

    stage = env == "test"
    vault_prefix = "VAULT_STAGING_" if stage else "VAULT_"
    return Settings(
        output_dir=_path(os.environ.get("FORGE_OUTPUT_DIR"), data / "output"),
        db_path=_path(os.environ.get("FORGE_DB_PATH"), data / "data" / "forge.db"),
        typst_bin=os.environ.get("FORGE_TYPST_BIN") or None,
        anthropic_api_key=sec("ANTHROPIC_API_KEY") or None,
        openai_api_key=sec("OPENAI_API_KEY") or None,
        gemini_api_key=sec("GEMINI_API_KEY") or None,
        llm_provider=os.environ.get("FORGE_LLM_PROVIDER") or "anthropic",
        vault_url=os.environ.get(vault_prefix + "URL", "").strip(),
        vault_token=sec(vault_prefix + "ADMIN_TOKEN"),
        vault_answer_key=sec(vault_prefix + "ANSWER_KEY"),
        vault_domain=os.environ.get(vault_prefix + "DOMAIN", "").strip(),
        env=env,
        data_dir=data,
        config_dir=conf_dir,
        config_file=cfg,
        sku_provider=(os.environ.get("FORGE_SKU_PROVIDER") or ("dev" if stage else "hub")).lower(),
        telegram_bot_token=sec("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        web_host=os.environ.get("FORGE_WEB_HOST", "127.0.0.1").strip(),
        web_port=int(os.environ.get("FORGE_WEB_PORT", "8710")),
        backup_remote=os.environ.get("FORGE_BACKUP_REMOTE", "").strip(),
    )
