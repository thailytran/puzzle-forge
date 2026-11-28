"""P10.1: one version source, release workflows wired to the tags."""

from __future__ import annotations

import tomllib

import yaml

from forge import __version__
from forge.config import REPO_ROOT
from forge.version import version_line


def _pyver(path: str) -> str:
    return str(tomllib.loads((REPO_ROOT / path).read_text())["project"]["version"])


def test_version_single_source() -> None:
    v = _pyver("pyproject.toml")
    assert __version__ == v
    parts = v.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)
    assert version_line().startswith(f"puzzle-forge {v}")


def test_changelog_has_unreleased_and_current_version() -> None:
    text = (REPO_ROOT / "docs" / "CHANGELOG.md").read_text()
    assert "## [Unreleased]" in text
    assert f"## [{_pyver('pyproject.toml')}]" in text


def test_workflows() -> None:
    wf = REPO_ROOT / ".github" / "workflows"
    rel = yaml.safe_load((wf / "release.yml").read_text())
    assert rel[True]["push"]["tags"] == ["v*.*.*"]  # yaml 1.1 reads "on" as True
    img = yaml.safe_load((wf / "casevault-image.yml").read_text())
    assert img[True]["push"]["tags"] == ["casevault-v*.*.*"]
    steps = img["jobs"]["image"]["steps"]
    assert any("build-push-action" in s.get("uses", "") for s in steps)
    import casevault

    assert casevault.__version__ == _pyver("apps/casevault/pyproject.toml")
