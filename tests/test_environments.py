"""P10.2: FORGE_ENV profiles, system paths, encrypted secret store."""

from __future__ import annotations

import json

import pytest

from forge.config import get_settings
from forge.publish.sku import SkuError, provider_from_env
from forge.secrets import SecretStore, mask
from forge.vault.sync import sender_for

ENV_KEYS = (
    "FORGE_ENV",
    "FORGE_DATA_DIR",
    "FORGE_CONFIG",
    "FORGE_CONFIG_DIR",
    "FORGE_SKU_PROVIDER",
    "FORGE_DB_PATH",
    "FORGE_OUTPUT_DIR",
    "VAULT_URL",
    "VAULT_STAGING_URL",
    "VAULT_STAGING_ADMIN_TOKEN",
    "ANTHROPIC_API_KEY",
)


@pytest.fixture
def clean(monkeypatch, tmp_path):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    cfg = tmp_path / "forge.env"
    cfg.write_text("")
    monkeypatch.setenv("FORGE_CONFIG", str(cfg))
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path / "var"))
    return tmp_path


def test_paths_follow_data_dir(clean):
    st = get_settings()
    assert st.env == "dev"
    assert st.db_path == clean / "var" / "data" / "forge.db"
    assert st.output_dir == clean / "var" / "output"
    assert st.config_dir == clean / "var" / "data" / "config"


def test_test_env_uses_dev_sku_and_staging_vault(clean, monkeypatch):
    monkeypatch.setenv("FORGE_ENV", "test")
    monkeypatch.setenv("VAULT_URL", "https://casevault.example.com")
    monkeypatch.setenv("VAULT_STAGING_URL", "mock")
    monkeypatch.setenv("VAULT_STAGING_ADMIN_TOKEN", "staging-token")
    st = get_settings()
    assert st.sku_provider == "dev" and st.vault_url == "mock"
    assert st.vault_token == "staging-token"
    assert type(provider_from_env(st.db_path)).__name__ == "DevSkuProvider"
    send = sender_for(st.vault_url, "", st.data_dir)
    send({"book_id": "bk-1", "title": "x"})
    assert json.loads((st.data_dir / "vault_mock" / "bk-1.json").read_text())["title"] == "x"


def test_prod_refuses_dev_sku(clean, monkeypatch):
    monkeypatch.setenv("FORGE_ENV", "prod")
    monkeypatch.setenv("FORGE_SKU_PROVIDER", "dev")
    with pytest.raises(SkuError, match="prod"):
        provider_from_env(clean / "f.db")
    monkeypatch.setenv("FORGE_ENV", "staging")
    with pytest.raises(ValueError, match="FORGE_ENV"):
        get_settings()


def test_secret_store_encrypted_and_env_wins(clean, monkeypatch):
    store = SecretStore(clean / "conf")
    store.set("ANTHROPIC_API_KEY", "sk-ant-secret-123456")
    raw = (clean / "conf" / "secrets.enc").read_bytes()
    assert b"sk-ant" not in raw
    assert oct((clean / "conf" / "secrets.enc").stat().st_mode & 0o777) == "0o600"
    assert oct((clean / "conf" / "secret.key").stat().st_mode & 0o777) == "0o600"
    assert store.get("ANTHROPIC_API_KEY") == "sk-ant-secret-123456"
    assert store.masked()["ANTHROPIC_API_KEY"] == {"source": "store", "masked": "sk-a…3456"}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env-xyz")
    assert store.get("ANTHROPIC_API_KEY") == "from-env-xyz"
    monkeypatch.setenv("FORGE_CONFIG_DIR", str(clean / "conf"))
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert get_settings().anthropic_api_key == "sk-ant-secret-123456"
    store.set("ANTHROPIC_API_KEY", "")
    assert store.get("ANTHROPIC_API_KEY") == ""
    assert mask("abc") == "•••"
