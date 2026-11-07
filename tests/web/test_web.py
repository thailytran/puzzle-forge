"""P10.4: job queue, worker, web UI (login, dashboard, new book, book page, settings)."""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from forge.config import get_settings
from forge.jobs import JobQueue, run_one
from forge.secrets import SecretStore
from forge.web.app import create_app, spec_from_form
from forge.web.auth import hash_password

PW = "correct-horse-battery"


@pytest.fixture
def env(tmp_path, monkeypatch):
    for k in (
        "FORGE_DB_PATH",
        "FORGE_OUTPUT_DIR",
        "FORGE_CONFIG_DIR",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "VAULT_URL",
    ):
        monkeypatch.delenv(k, raising=False)
    cfg = tmp_path / "forge.env"
    cfg.write_text("FORGE_ENV=test\n")
    monkeypatch.setenv("FORGE_CONFIG", str(cfg))
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("FORGE_ENV", "test")
    st = get_settings()
    SecretStore(st.config_dir).set("FORGE_WEB_PASSWORD_HASH", hash_password(PW))
    client = TestClient(create_app(st))
    return st, client


def login(client):
    r = client.post("/login", data={"password": PW}, follow_redirects=False)
    assert r.status_code == 303
    return client


def test_login_required_and_lockout(env):
    _st, c = env
    assert c.get("/", follow_redirects=False).status_code == 303
    assert c.get("/api/health").json() == {"ok": True, "env": "test"}
    for _ in range(5):
        assert c.post("/login", data={"password": "nope"}).status_code == 401
    assert c.post("/login", data={"password": PW}).status_code == 429


def test_spec_from_form_validation():
    s = spec_from_form(
        {
            "title": "Ocean Fun",
            "line": "classic_mixed",
            "audience": "adult",
            "content_pages": "20",
            "themes": "ocean, space",
            "seed": "4",
        }
    )
    assert s["book"]["seed"] == 4 and s["puzzles"]["themes"] == ["ocean", "space"]
    assert len(s["puzzles"]["types"]) == 6
    with pytest.raises(ValueError):
        spec_from_form({"title": "x", "line": "escape"})
    with pytest.raises(ValueError):
        spec_from_form({"title": " ", "line": "classic_sudoku"})


@pytest.mark.typst
def test_new_book_job_runs_to_qa_passed_and_shows_up(env):
    st, c = login(env[1]) and env
    r = c.post(
        "/new",
        data={
            "title": "Web Sudoku",
            "line": "classic_sudoku",
            "audience": "adult",
            "content_pages": "4",
            "seed": "11",
            "mode": "progressive",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    q = JobQueue(st.db_path)
    job = run_one(q, st, notify=None)
    q.close()
    assert job is not None and job.status == "done", job.log[-2000:]
    assert '"qa": "PASSED"' in job.result
    page = c.get("/").text
    assert "Web Sudoku" in page and "QA_PASSED" in page
    book = c.get(f"/books/{job.book_id}").text
    assert "Báo cáo QA" in book and "interior.pdf" in book
    pdf = c.get(f"/books/{job.book_id}/files/interior.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert c.get(f"/books/{job.book_id}/files/../../etc/passwd").status_code == 404
    r = c.post(f"/books/{job.book_id}/review", data={"action": "approve"})
    assert "only MANUAL_REVIEW" in r.text  # QA_PASSED -> SKU -> metadata first


def test_csv_upload_and_failed_job(env):
    st, c = env
    login(c)
    csv_text = (
        "line,title,audience,content_pages,seed\nclassic_sudoku,A,adult,4,1\nnope,B,adult,4,2\n"
    )
    r = c.post("/new/csv", files={"file": ("b.csv", csv_text.encode())})
    assert r.status_code == 422 and "dòng 3" in r.text
    q = JobQueue(st.db_path)
    assert q.counts() == {"queued": 1}
    q.add("qa_run", {"out_dir": str(st.output_dir / "missing")}, "QA missing")
    q.c.execute("DELETE FROM jobs WHERE kind='build_book'")
    q.c.commit()
    job = run_one(q, st, notify=None)
    assert job is not None and job.status == "failed" and "Traceback" in job.log
    q.close()


def test_settings_secrets_routing_env_brand(env, monkeypatch):
    st, c = env
    login(c)
    page = c.get("/settings").text
    assert "ANTHROPIC_API_KEY" in page and "case_bible" in page
    c.post("/settings/secret", data={"name": "OPENAI_API_KEY", "value": "sk-test-abcdef123456"})
    assert "sk-t…3456" in c.get("/settings").text
    assert SecretStore(st.config_dir).get("OPENAI_API_KEY") == "sk-test-abcdef123456"
    assert c.post("/settings/secret", data={"name": "EVIL", "value": "x"}).status_code == 400
    assert "chưa có key" in c.get("/settings/ai/test/gemini").text
    c.post(
        "/settings/ai/routing",
        data={"story.provider": "gemini", "story.model": "g-x", "budget.daily_usd": "0.7"},
    )
    saved = yaml.safe_load((st.config_dir / "ai_routing.yaml").read_text())
    assert saved["tasks"]["story"]["model"] == "g-x"
    assert saved["budget_by_env"]["test"]["daily_usd"] == 0.7
    c.post("/settings/env", data={"VAULT_STAGING_URL": "mock", "TELEGRAM_CHAT_ID": "42"})
    text = st.config_file.read_text()
    assert "VAULT_STAGING_URL=mock" in text and "TELEGRAM_CHAT_ID=42" in text
    c.post("/settings/brand", data={"brand_name": "Halospark Inc", "website": "halosparkinc.com"})
    from forge.editions.brand import load_brand

    monkeypatch.setenv("FORGE_CONFIG_DIR", str(st.config_dir))
    assert load_brand().name == "Halospark Inc"


def test_cli_web_refuses_public_host(env):
    from typer.testing import CliRunner

    from forge.cli import app

    r = CliRunner().invoke(app, ["web", "run", "--host", "0.0.0.0"])
    assert r.exit_code == 2 and "refused" in r.output
    r = CliRunner().invoke(app, ["worker", "--once"])
    assert r.exit_code == 0
