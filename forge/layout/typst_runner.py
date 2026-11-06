"""Compile Typst documents.

Backend order: the `typst` CLI (FORGE_TYPST_BIN or PATH) → the `typst` Python package
(Apache-2.0, same compiler embedded) as a fallback. System fonts are ignored so a book
renders identically on every machine: only `assets/fonts/` + Typst's embedded fonts are used.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from forge.config import REPO_ROOT

FONT_DIR = REPO_ROOT / "assets" / "fonts"
TEMPLATE_DIR = REPO_ROOT / "templates" / "typst"

Backend = Literal["cli", "python"]


class TypstError(RuntimeError):
    pass


def find_typst() -> str | None:
    """Path to the typst CLI, or None."""
    explicit = os.environ.get("FORGE_TYPST_BIN")
    if explicit:
        return explicit if os.path.isfile(explicit) and os.access(explicit, os.X_OK) else None
    return shutil.which("typst")


def python_typst_available() -> bool:
    return importlib.util.find_spec("typst") is not None


def backend() -> Backend | None:
    if find_typst():
        return "cli"
    if python_typst_available():
        return "python"
    return None


def typst_version() -> str | None:
    """Human-readable version of the active backend."""
    cli = find_typst()
    if cli:
        out = subprocess.run([cli, "--version"], capture_output=True, text=True, check=False)
        return out.stdout.strip() or None
    if python_typst_available():
        import importlib.metadata as md

        return f"typst (python package) {md.version('typst')}"
    return None


def compile_pdf(
    main: Path,
    output: Path,
    *,
    root: Path | None = None,
    inputs: dict[str, str] | None = None,
    font_dirs: list[Path] | None = None,
    prefer: Backend | None = None,
) -> Path:
    """Compile `main` (.typ) to `output` (.pdf). Raises TypstError on failure."""
    root = root or main.parent
    fonts = [str(p) for p in (font_dirs if font_dirs is not None else [FONT_DIR])]
    inputs = inputs or {}
    chosen = prefer or backend()
    output.parent.mkdir(parents=True, exist_ok=True)
    if chosen == "cli":
        cli = find_typst()
        if cli is None:
            raise TypstError("typst CLI not found")
        cmd = [cli, "compile", "--root", str(root), "--ignore-system-fonts"]
        for f in fonts:
            cmd += ["--font-path", f]
        for k, v in inputs.items():
            cmd += ["--input", f"{k}={v}"]
        cmd += [str(main), str(output)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise TypstError(proc.stderr.strip() or "typst compile failed")
        return output
    if chosen == "python":
        import typst

        try:
            typst.compile(
                str(main),
                output=str(output),
                root=str(root),
                font_paths=fonts,
                ignore_system_fonts=True,
                sys_inputs=inputs,
            )
        except Exception as exc:  # typst.TypstError and friends
            raise TypstError(str(exc)) from exc
        return output
    raise TypstError("no Typst backend: install the typst CLI (scripts/setup_vm.sh) or `uv sync`")
