"""`forge` command-line entry point."""

from __future__ import annotations

import typer

from forge import __version__

app = typer.Typer(
    name="forge",
    help="Puzzle Forge: build print-ready puzzle books for Amazon KDP.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"puzzle-forge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Puzzle Forge CLI."""


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(f"puzzle-forge {__version__}")


if __name__ == "__main__":
    app()
