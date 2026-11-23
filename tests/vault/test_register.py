"""`forge vault register` (HALOSPARK Studio calls it when the owner approves a puzzle-story book)."""

from typer.testing import CliRunner

from forge.cli import app

runner = CliRunner()


def test_register_without_vault_yaml_exits_1(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("FORGE_DB_PATH", str(tmp_path / "x.db"))
    (tmp_path / "book").mkdir()
    result = runner.invoke(app, ["vault", "register", str(tmp_path / "book")])
    assert result.exit_code == 1
    assert "no vault.yaml" in result.output
