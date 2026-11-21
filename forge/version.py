"""Version info: semver from pyproject (installed metadata), git sha, environment."""

from __future__ import annotations

import os
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def package_version() -> str:
    try:
        return version("puzzle-forge")
    except PackageNotFoundError:  # running from a plain checkout
        import tomllib

        return str(tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["version"])


def git_sha() -> str:
    info = REPO / "BUILD_INFO"  # written by scripts/install.sh for tarball installs
    if info.is_file():
        for line in info.read_text().splitlines():
            if line.startswith("sha="):
                return line[4:].strip()
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def version_line() -> str:
    sha = git_sha()
    env = os.environ.get("FORGE_ENV", "dev")
    return f"puzzle-forge {package_version()}" + (f" ({sha})" if sha else "") + f" env={env}"
