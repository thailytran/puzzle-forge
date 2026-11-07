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


@app.command()
def puzzle(
    type_: str = typer.Argument(..., metavar="TYPE", help="Puzzle type, e.g. wordsearch"),
    level: str = typer.Option("easy", help="very_easy | easy | medium | hard | expert"),
    audience: str = typer.Option("adult", help="kids_6_8 | kids_9_12 | teen | adult | ..."),
    theme: str | None = typer.Option(None, help="Built-in theme (see forge/wordlists/data)"),
    words: str | None = typer.Option(None, help="Comma-separated explicit word list"),
    seed: int = typer.Option(1, help="Seed (same seed => same puzzle)"),
    hidden_message: str | None = typer.Option(None, help="Word search: leftover letters"),
    shape: str | None = typer.Option(None, help="Word search mask: rect | circle | diamond"),
    option: list[str] = typer.Option(
        [], "--option", "-o", help="Type option key=value (e.g. size=6), repeatable"
    ),
    trim: str = typer.Option("8.5x11", help="Trim for the preview PDF"),
    out: Path = typer.Option(Path("output/tmp"), help="Output directory"),
) -> None:
    """Generate one puzzle -> puzzle.json + preview.pdf (puzzle + solution page)."""
    from pydantic import ValidationError

    from forge.core.models import PuzzleSpec
    from forge.layout.typst_runner import TypstError
    from forge.puzzles.base import GenerationError
    from forge.puzzles.preview import preview_pdf
    from forge.puzzles.registry import get_puzzle_type

    constraints = []
    if hidden_message:
        constraints.append({"kind": "hidden_message", "text": hidden_message})
    options: dict[str, object] = {"shape": shape} if shape else {}
    for kv in option:
        key, _, val = kv.partition("=")
        options[key.strip()] = int(val) if val.strip().lstrip("-").isdigit() else val.strip()
    try:
        spec = PuzzleSpec.model_validate(
            {
                "type": type_,
                "level": level,
                "audience": audience,
                "theme": theme,
                "words": [w.strip() for w in words.split(",")] if words else None,
                "options": options,
                "constraints": constraints,
            }
        )
        pz = get_puzzle_type(type_).generate(spec, seed)
    except (ValidationError, KeyError, ValueError, GenerationError) as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    out.mkdir(parents=True, exist_ok=True)
    (out / "puzzle.json").write_text(pz.model_dump_json(indent=1), encoding="utf-8")
    d = pz.difficulty
    typer.echo(
        f"{pz.id}  verify={'OK' if pz.verify and pz.verify.ok else 'FAIL'}  "
        f"difficulty={d.score if d else '?'} ({d.label if d else '?'})"
    )
    if pz.token:
        typer.echo(f"token: {pz.token}")
    try:
        pdf = preview_pdf(pz, out / "preview.pdf", trim=trim)
        typer.echo(f"wrote {out / 'puzzle.json'} and {pdf}")
    except TypstError as exc:
        typer.secho(f"preview skipped: {exc}", fg=typer.colors.YELLOW, err=True)


book_app = typer.Typer(help="Build and verify whole books.")
app.add_typer(book_app, name="book")


@book_app.command("build")
def book_build(
    spec_path: Path = typer.Argument(..., help="Book YAML (configs/books/...)"),
    no_render: bool = typer.Option(False, "--no-render", help="Skip the PDF (plan + puzzles only)"),
) -> None:
    """Generate all puzzles (verified, catalog-unique) and render interior.pdf + manifest.json."""
    from forge.book.builder import BuildError, build_book
    from forge.core.book import load_book_spec
    from forge.layout.typst_runner import TypstError

    settings = get_settings()
    try:
        out = build_book(
            load_book_spec(spec_path), settings.output_dir, settings.db_path, render=not no_render
        )
    except (BuildError, TypstError, FileNotFoundError, ValueError) as exc:
        typer.secho(f"build failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"built {out}")


@book_app.command("verify")
def book_verify(out_dir: Path = typer.Argument(..., help="output/<book_id>")) -> None:
    """Re-verify every puzzle of a built book with its independent solver."""
    from forge.book.builder import verify_book

    problems = verify_book(out_dir)
    for p in problems:
        typer.secho(p, fg=typer.colors.RED)
    if problems:
        raise typer.Exit(1)
    typer.secho("all puzzles verified", fg=typer.colors.GREEN)


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
