from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from forge.config import REPO_ROOT
from forge.doctor import TYPST_PINNED

SCRIPTS = sorted((REPO_ROOT / "scripts").glob("*.sh"))


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash missing")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_bash_syntax(script) -> None:  # type: ignore[no-untyped-def]
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_scripts_executable() -> None:
    assert SCRIPTS
    for s in SCRIPTS:
        assert s.stat().st_mode & 0o111, f"{s.name} not executable"


def test_typst_version_pinned_consistently() -> None:
    setup = (REPO_ROOT / "scripts/setup_vm.sh").read_text()
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    m1 = re.search(r'TYPST_VERSION="([\d.]+)"', setup)
    m2 = re.search(r'TYPST_VERSION: "([\d.]+)"', ci)
    assert m1 and m2
    assert m1.group(1) == m2.group(1) == TYPST_PINNED


def test_no_cloud_paths_in_scripts() -> None:
    for s in SCRIPTS:
        text = s.read_text()
        assert "/home/user" not in text
        assert "/tmp/claude" not in text
