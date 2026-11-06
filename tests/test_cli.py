from typer.testing import CliRunner

from forge import __version__
from forge.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Puzzle Forge" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_registry_stats(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FORGE_DB_PATH", str(tmp_path / "x.db"))
    result = runner.invoke(app, ["registry", "stats"])
    assert result.exit_code == 0, result.output
    assert "total: 0" in result.output
