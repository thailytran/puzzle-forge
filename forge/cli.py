"""`forge` command-line entry point."""

from __future__ import annotations

from pathlib import Path

import typer

from forge import __version__
from forge.config import get_settings
from forge.core.registry import Registry

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


@app.command()
def doctor() -> None:
    """Check this machine: Python, Typst, fonts, output dir, DB, API keys."""
    from rich.console import Console
    from rich.table import Table

    from forge.doctor import run_all

    styles = {"ok": "[green]OK[/green]", "warn": "[yellow]WARN[/yellow]", "fail": "[red]FAIL[/red]"}
    results = run_all(get_settings())
    table = Table(title="forge doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for r in results:
        table.add_row(r.name, styles[r.status], r.detail)
    Console().print(table)
    if any(r.status == "fail" for r in results):
        raise typer.Exit(1)


registry_app = typer.Typer(help="Inspect the puzzle registry (duplicate guard).")
app.add_typer(registry_app, name="registry")


@registry_app.command("stats")
def registry_stats() -> None:
    """Count registered puzzles per type."""
    settings = get_settings()
    with Registry(settings.db_path) as reg:
        stats = reg.stats()
        books = reg.books()
    typer.echo(f"db: {settings.db_path}")
    typer.echo(f"books: {len(books)}")
    for type_, n in stats.items():
        typer.echo(f"  {type_}: {n}")
    typer.echo(f"total: {sum(stats.values())}")


@registry_app.command("list")
def registry_list(book_id: str = typer.Argument(..., help="Book id")) -> None:
    """List puzzles registered for a book."""
    with Registry(get_settings().db_path) as reg:
        for e in reg.list_by_book(book_id):
            typer.echo(f"{e.puzzle_id}\t{e.level}\tseed={e.seed}")


layout_app = typer.Typer(help="Layout / Typst pipeline tools.")
app.add_typer(layout_app, name="layout")


@layout_app.command("demo")
def layout_demo(
    trim: str = typer.Option("8.5x11", help="8.5x11 | 8x10 | 6x9 | 8.5x8.5"),
    large_print: bool = typer.Option(False, "--large-print", help="Bigger fonts and cells."),
    out: Path = typer.Option(Path("output/layout_demo"), help="Output directory."),
) -> None:
    """Render a sample interior PDF to check the Typst pipeline."""
    from forge.layout.demo import demo_layout
    from forge.layout.document import render_pdf
    from forge.layout.typst_runner import TypstError, backend

    doc = demo_layout(trim, large_print=large_print)
    try:
        pdf = render_pdf(doc, out / "interior.pdf")
    except (TypstError, ValueError) as exc:
        typer.secho(f"layout demo failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"wrote {pdf} ({len(doc.pages)} pages, trim {trim}, backend {backend()})")


if __name__ == "__main__":
    app()
