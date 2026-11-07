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
    plan_path: Path | None = typer.Option(
        None, "--plan", help="content_plan.yaml (sub-themes, words)"
    ),
) -> None:
    """Generate all puzzles (verified, catalog-unique) and render interior.pdf + manifest.json.

    With --plan (or an existing output/<book>/content_plan.yaml) every page uses its own sub-theme,
    words and quotes from the plan; edit the YAML and rebuild to regenerate the puzzles."""
    from forge.book.builder import BuildError, build_book
    from forge.core.book import load_book_spec
    from forge.layout.typst_runner import TypstError

    settings = get_settings()
    try:
        from forge.book.content_plan import load_plan

        plan = load_plan(plan_path) if plan_path else None
        out = build_book(
            load_book_spec(spec_path),
            settings.output_dir,
            settings.db_path,
            render=not no_render,
            plan=plan,
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


qa_app = typer.Typer(help="QA gate (docs/QA_SPEC.md).")
app.add_typer(qa_app, name="qa")


@qa_app.command("run")
def qa_run(
    out_dir: Path = typer.Argument(..., help="output/<book_id>"),
    fix_rounds: int = typer.Option(3, help="Auto-fix rounds (regenerate failing puzzles)"),
    layers: str = typer.Option("", help="Comma list, e.g. L1,L2 (default: all)"),
) -> None:
    """Run all QA checks; writes qa/qa_report.json + qa_report.html. Exit 1 unless PASSED."""
    from forge.qa.fixer import regenerate_failing
    from forge.qa.gate import run_gate

    sel = {x.strip() for x in layers.split(",") if x.strip()} or None
    report = run_gate(
        out_dir,
        get_settings().db_path,
        fixer=regenerate_failing,
        max_fix_rounds=fix_rounds,
        layers=sel,
    )
    for c in report.checks:
        if c.status == "fail":
            mark = "WAIVED" if c.waived else "FAIL"
            typer.secho(
                f"{mark:6} {c.level:7} {c.id}: {c.message}",
                fg=typer.colors.YELLOW if c.waived else typer.colors.RED,
            )
    color = typer.colors.GREEN if report.result == "PASSED" else typer.colors.RED
    typer.secho(f"{report.result}  {report.counts}", fg=color)
    typer.echo(f"report: {out_dir / 'qa' / 'qa_report.html'}")
    if report.result != "PASSED":
        raise typer.Exit(1)


@qa_app.command("waive")
def qa_waive(
    out_dir: Path = typer.Argument(...),
    check_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    by: str = typer.Option("owner", "--by"),
) -> None:
    """Waive a MINOR check for the current files (re-run `forge qa run` afterwards)."""
    from forge.qa.checks import REGISTRY
    from forge.qa.gate import load_check_modules
    from forge.qa.report import add_waiver

    load_check_modules()
    if check_id not in REGISTRY:
        typer.secho(f"unknown check {check_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    try:
        add_waiver(out_dir, check_id, reason, by, REGISTRY[check_id].level)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"waived {check_id}")


@book_app.command("status")
def book_status(out_dir: Path = typer.Argument(..., help="output/<book_id>")) -> None:
    """Show the book state, history and whether the QA report still matches the files."""
    import json as _json

    from forge.qa.gate import sync_state
    from forge.qa.report import load, report_valid
    from forge.qa.state import StateStore

    book_id = _json.loads((out_dir / "manifest.json").read_text())["book_id"]
    with StateStore(get_settings().db_path) as store:
        state = sync_state(store, book_id, out_dir)
        history = store.history(book_id)
    rep = load(out_dir)
    typer.echo(f"{book_id}: {state}")
    if rep:
        valid = (
            "valid" if report_valid(out_dir) else ("stale" if rep.result == "PASSED" else "failed")
        )
        typer.echo(f"QA report {rep.run_id}: {rep.result} ({valid})")
    for ev in history[-10:]:
        typer.echo(f"  {ev.at}  {ev.from_state or '-'} -> {ev.to_state}  [{ev.actor}] {ev.note}")


@app.command("review-pack")
def review_pack(
    code: str = typer.Argument(..., help="Milestone code, e.g. P1.8"),
    out_dirs: list[Path] = typer.Argument(..., help="output/<book_id> folders"),
    root: Path = typer.Option(Path("review"), help="Where review/<code>.md is written"),
) -> None:
    """Write review/<code>.md checklist + key-page PNGs, PDF and QA report per book."""
    from forge.qa.review_pack import make_review

    md = make_review(code, out_dirs, root)
    typer.echo(f"wrote {md}")


@app.command()
def review(
    out_dir: Path = typer.Argument(..., help="output/<book_id>"),
    approve: bool = typer.Option(False, "--approve"),
    reject: bool = typer.Option(False, "--reject"),
    note: str = typer.Option("", "--note"),
    by: str = typer.Option("owner", "--by"),
) -> None:
    """Manual review (until the web UI): MANUAL_REVIEW -> APPROVED | REJECTED (+ note)."""
    import json as _json

    from forge.qa.gate import sync_state
    from forge.qa.state import IllegalTransition, StateStore

    if approve == reject:
        typer.secho("choose exactly one of --approve / --reject", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    book_id = _json.loads((out_dir / "manifest.json").read_text())["book_id"]
    with StateStore(get_settings().db_path) as store:
        state = sync_state(store, book_id, out_dir)
        if state != "MANUAL_REVIEW":
            typer.secho(
                f"{book_id} is {state}; only MANUAL_REVIEW books can be reviewed "
                "(QA_PASSED -> SKU -> metadata first, see docs/QA_SPEC.md)",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            store.transition(book_id, "APPROVED" if approve else "REJECTED", actor=by, note=note)
            if reject:
                store.transition(book_id, "DRAFT", actor=by, note="rejected: " + note)
        except IllegalTransition as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc
    typer.echo(f"{book_id}: {'APPROVED' if approve else 'REJECTED -> DRAFT'}")


sku_app = typer.Typer(help="SKU from the HALOSPARK Product Hub (configs/sku.yaml).")
app.add_typer(sku_app, name="sku")


@sku_app.command("assign")
def sku_assign(out_dir: Path = typer.Argument(..., help="output/<book_id>")) -> None:
    """QA_PASSED book -> SKU from the Hub shared counter -> SKU_ASSIGNED (idempotent)."""
    import json as _json

    from forge.ports import SkuError
    from forge.publish.sku import assign_sku, existing_sku, provider_from_env
    from forge.qa.gate import sync_state
    from forge.qa.state import StateStore

    settings = get_settings()
    book_id = _json.loads((out_dir / "manifest.json").read_text())["book_id"]
    with StateStore(settings.db_path) as store:
        state = sync_state(store, book_id, out_dir)
        if state != "QA_PASSED" and not (state == "SKU_ASSIGNED" and existing_sku(out_dir)):
            typer.secho(
                f"{book_id} is {state}; run `forge qa run` until QA_PASSED first",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        try:
            data = assign_sku(out_dir, provider_from_env(settings.db_path))
        except SkuError as exc:
            typer.secho(f"SKU failed: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from exc
        if state == "QA_PASSED":
            store.transition(book_id, "SKU_ASSIGNED", note=data["sku"])
    typer.echo(f"{book_id}: {data['sku']} ({data['provider']})")


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
