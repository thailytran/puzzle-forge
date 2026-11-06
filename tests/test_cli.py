import pytest
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


@pytest.mark.typst
def test_layout_demo(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["layout", "demo", "--trim", "6x9", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "interior.pdf").is_file()


def test_layout_demo_bad_trim(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["layout", "demo", "--trim", "5x5", "--out", str(tmp_path)])
    assert result.exit_code == 1


def test_puzzle_wordsearch(tmp_path) -> None:  # type: ignore[no-untyped-def]
    args = ["puzzle", "wordsearch", "--theme", "animals", "--seed", "3", "--out", str(tmp_path)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "verify=OK" in result.output
    assert (tmp_path / "puzzle.json").is_file()


def test_puzzle_unknown_type(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["puzzle", "nope", "--out", str(tmp_path)])
    assert result.exit_code == 1
