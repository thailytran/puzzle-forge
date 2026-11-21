"""P10.7: smoke test end to end (staging = in-process casevault app, mocked providers)."""

from __future__ import annotations

import pytest

from forge.config import get_settings
from forge.smoke import SmokeError, run_smoke

pytestmark = pytest.mark.typst


@pytest.fixture
def env(tmp_path, monkeypatch):
    cfg = tmp_path / "forge.env"
    cfg.write_text("")
    for k in ("FORGE_DB_PATH", "FORGE_OUTPUT_DIR", "FORGE_CONFIG_DIR", "FORGE_SKU_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("FORGE_CONFIG", str(cfg))
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("FORGE_ENV", "test")
    monkeypatch.setenv("VAULT_STAGING_ANSWER_KEY", "k-staging")
    monkeypatch.setenv("VAULT_STAGING_ADMIN_TOKEN", "t-staging")
    return tmp_path


def test_refuses_outside_test_env(env, monkeypatch):
    monkeypatch.setenv("FORGE_ENV", "dev")
    with pytest.raises(SmokeError, match="FORGE_ENV=test"):
        run_smoke(get_settings(), log=lambda m: None)


def test_smoke_with_mock_vault(env, monkeypatch):
    monkeypatch.setenv("VAULT_STAGING_URL", "mock")
    st = get_settings()
    res = run_smoke(st, log=lambda m: None)
    assert res["redeem"] == "skipped (mock)"
    assert (st.data_dir / "vault_mock" / f"{res['escape']}.json").is_file()


def test_smoke_against_staging_site(env, monkeypatch):
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

    class Turnstile:
        def verify(self, token, ip):
            return token == "XXXX.DUMMY.TOKEN.XXXX"

    events = []

    class Klaviyo(Null):
        def event(self, name, email, props, uid):
            events.append((name, email))

    s = Settings(
        database_url=f"sqlite:///{env}/cv.db",
        public_url="https://staging.test",
        admin_api_token="t-staging",
        answer_key="k-staging",
        secure_cookies=False,
        rules=load_rules(),
    )
    client = TestClient(
        create_app(
            s,
            Providers(NoEtsy(), Null(), Klaviyo(), Null(), Turnstile()),
            T.make_engine(s.database_url),
        )
    )

    def sender(url, token):
        def send(payload):
            r = client.post(
                "/api/admin/books", json=payload, headers={"Authorization": f"Bearer {token}"}
            )
            r.raise_for_status()
            return r.json()

        return send

    monkeypatch.setattr("forge.vault.sync.http_sender", sender)
    monkeypatch.setenv("VAULT_STAGING_URL", "https://staging.test")
    monkeypatch.setenv("VAULT_STAGING_DOMAIN", "staging.test")
    posted = {}

    def post(url, form):
        posted["url"] = url
        r = client.post(url.removeprefix("https://staging.test"), data=form)
        app = client.app
        app.state.vault.process_outbox()
        return r.text

    res = run_smoke(get_settings(), email="owner@example.com", post=post, log=lambda m: None)
    assert res["redeem"].startswith("Case solved")
    assert posted["url"].endswith(f"/solve/{res['escape']}")
    assert ("Case Solved", "owner@example.com") in events
