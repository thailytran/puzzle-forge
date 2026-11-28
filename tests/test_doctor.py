from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import doctor
from forge.cli import app
from forge.config import get_settings


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FORGE_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("FORGE_DB_PATH", str(tmp_path / "data" / "forge.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


def test_python_ok() -> None:
    assert doctor.check_python().status == "ok"


def test_python_too_old() -> None:
    assert doctor.check_python((3, 11, 0)).status == "fail"


def test_output_writable(env: Path) -> None:
    r = doctor.check_output_dir(get_settings())
    assert r.status == "ok"
    assert (env / "out").is_dir()


def test_output_not_writable(env: Path) -> None:
    blocker = env / "blocker"
    blocker.write_text("file, not dir")
    s = get_settings()
    s = s.__class__(**{**s.__dict__, "output_dir": blocker / "sub"})
    assert doctor.check_output_dir(s).status == "fail"


def test_db(env: Path) -> None:
    assert doctor.check_db(get_settings()).status == "ok"


def test_fonts_ok() -> None:
    assert doctor.check_fonts().status == "ok"


def test_fonts_missing(tmp_path: Path) -> None:
    assert doctor.check_fonts(tmp_path).status == "fail"


def test_api_keys_missing_is_warning(env: Path) -> None:
    r = doctor.check_api_keys(get_settings())
    assert r.status == "warn"


def test_api_keys_present(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    r = doctor.check_api_keys(get_settings())
    assert r.status == "ok"
    assert "sk-test" not in r.detail


def test_typst_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "backend", lambda: None)
    assert doctor.check_typst().status == "fail"


def test_typst_python_fallback_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "backend", lambda: "python")
    monkeypatch.setattr(doctor, "typst_version", lambda: "typst (python package) 0.14.9")
    assert doctor.check_typst().status == "warn"


def test_typst_cli_version_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "backend", lambda: "cli")
    monkeypatch.setattr(doctor, "typst_version", lambda: "typst 0.12.0 (abc)")
    assert doctor.check_typst().status == "warn"
    monkeypatch.setattr(doctor, "typst_version", lambda: f"typst {doctor.TYPST_PINNED} (abc)")
    assert doctor.check_typst().status == "ok"


@pytest.mark.typst
def test_render_smoke(env: Path) -> None:
    assert doctor.check_render().status == "ok"


def test_cli_doctor_exit_code(env: Path) -> None:
    result = CliRunner().invoke(app, ["doctor"])
    assert "Python" in result.output
    results = doctor.run_all(get_settings())
    expected = 1 if any(r.status == "fail" for r in results) else 0
    assert result.exit_code == expected
