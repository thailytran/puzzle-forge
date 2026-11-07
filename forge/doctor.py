"""`forge doctor`: self-check of the machine (run after scripts/setup_vm.sh)."""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge.config import REPO_ROOT, Settings
from forge.layout.typst_runner import FONT_DIR, TypstError, backend, compile_pdf, typst_version

# Keep in sync with TYPST_VERSION in scripts/setup_vm.sh and .github/workflows/ci.yml
TYPST_PINNED = "0.14.2"
REQUIRED_FONTS = ("AtkinsonHyperlegible-Regular.ttf", "CourierPrime-Regular.ttf")

Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str


def check_python(version: tuple[int, ...] | None = None) -> CheckResult:
    v = version or tuple(sys.version_info[:3])
    text = ".".join(map(str, v))
    if v >= (3, 12):
        return CheckResult("Python", "ok", text)
    return CheckResult("Python", "fail", f"{text} (need ≥ 3.12; run scripts/setup_vm.sh)")


def check_typst() -> CheckResult:
    b = backend()
    if b is None:
        return CheckResult("Typst", "fail", "not found — run scripts/setup_vm.sh")
    ver = typst_version() or "?"
    if b == "python":
        return CheckResult("Typst", "warn", f"CLI missing, using fallback: {ver}")
    if TYPST_PINNED not in ver:
        return CheckResult("Typst", "warn", f"{ver} (pinned {TYPST_PINNED})")
    return CheckResult("Typst", "ok", ver)


def check_fonts(font_dir: Path = FONT_DIR) -> CheckResult:
    missing = [f for f in REQUIRED_FONTS if not (font_dir / f).is_file()]
    if missing:
        return CheckResult("Fonts", "fail", f"missing in {font_dir}: {', '.join(missing)}")
    n = len(list(font_dir.glob("*.ttf")) + list(font_dir.glob("*.otf")))
    return CheckResult("Fonts", "ok", f"{n} font files in {font_dir}")


def check_output_dir(settings: Settings) -> CheckResult:
    out = settings.output_dir
    try:
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=out, prefix=".doctor-"):
            pass
    except OSError as exc:
        return CheckResult("Output dir", "fail", f"{out}: {exc}")
    return CheckResult("Output dir", "ok", f"{out} writable")


def check_db(settings: Settings) -> CheckResult:
    from forge.core.registry import Registry

    try:
        with Registry(settings.db_path) as reg:
            total = sum(reg.stats().values())
    except Exception as exc:  # sqlite3.Error, OSError
        return CheckResult("Database", "fail", f"{settings.db_path}: {exc}")
    return CheckResult("Database", "ok", f"{settings.db_path} ({total} puzzles)")


def check_env_file(root: Path = REPO_ROOT, settings: Settings | None = None) -> CheckResult:
    f = settings.config_file if settings else Path.cwd() / ".env"
    if not f.is_file() and not (root / ".env").is_file():
        return CheckResult("Config file", "warn", f"missing — {f} (cp .env.example)")
    if f.is_file() and f.stat().st_mode & 0o077:
        return CheckResult("Config file", "warn", f"{f} readable by others: chmod 600 {f}")
    return CheckResult("Config file", "ok", str(f) if f.is_file() else str(root / ".env"))


def check_environment(settings: Settings) -> CheckResult:
    detail = f"FORGE_ENV={settings.env}, data={settings.data_dir}, SKU={settings.sku_provider}"
    if settings.is_prod and settings.sku_provider == "dev":
        return CheckResult("Environment", "fail", detail + " — prod must not use DEV SKUs")
    vault = settings.vault_url or "not set (registrations stay queued)"
    return CheckResult("Environment", "ok", f"{detail}, Case Vault={vault}")


def check_api_keys(settings: Settings) -> CheckResult:
    have = [
        name
        for name, val in (
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("GEMINI_API_KEY", settings.gemini_api_key),
        )
        if val
    ]
    if not have:
        return CheckResult("API keys", "warn", "none set (optional until phase P2)")
    return CheckResult("API keys", "ok", ", ".join(have) + " set")


def check_render() -> CheckResult:
    if backend() is None:
        return CheckResult("Render test", "fail", "no Typst backend")
    with tempfile.TemporaryDirectory() as tmp:
        main = Path(tmp) / "t.typ"
        main.write_text(
            '#set page(width: 6in, height: 9in)\n#text(font: "Atkinson Hyperlegible")[Doctor OK]\n',
            encoding="utf-8",
        )
        try:
            pdf = compile_pdf(main, Path(tmp) / "t.pdf")
        except TypstError as exc:
            return CheckResult("Render test", "fail", str(exc)[:200])
        size = pdf.stat().st_size
    return CheckResult("Render test", "ok", f"PDF compiled ({size} bytes)")


def run_all(settings: Settings) -> list[CheckResult]:
    checks: list[Callable[[], CheckResult]] = [
        check_python,
        check_typst,
        check_fonts,
        lambda: check_output_dir(settings),
        lambda: check_db(settings),
        lambda: check_env_file(REPO_ROOT, settings),
        lambda: check_environment(settings),
        lambda: check_api_keys(settings),
        check_render,
    ]
    return [c() for c in checks]
