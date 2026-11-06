from __future__ import annotations

import pytest

from forge.layout.typst_runner import backend


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked `typst` when no Typst backend (CLI or python package) exists."""
    if backend() is not None:
        return
    skip = pytest.mark.skip(reason="no typst backend installed")
    for item in items:
        if "typst" in item.keywords:
            item.add_marker(skip)
