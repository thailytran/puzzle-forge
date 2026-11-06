from __future__ import annotations

import os
import shutil

import pytest


def _typst_available() -> bool:
    explicit = os.environ.get("FORGE_TYPST_BIN")
    if explicit:
        return os.path.isfile(explicit) and os.access(explicit, os.X_OK)
    return shutil.which("typst") is not None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked `typst` when the typst binary is unavailable."""
    if _typst_available():
        return
    skip = pytest.mark.skip(reason="typst binary not installed")
    for item in items:
        if "typst" in item.keywords:
            item.add_marker(skip)
