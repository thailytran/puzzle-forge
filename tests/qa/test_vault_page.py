from __future__ import annotations

import json

import pytest

from forge.book.builder import build_book
from forge.core.book import BookSpec
from forge.qa.checks import REGISTRY, run_one
from forge.qa.gate import BookContext, run_gate

pytestmark = pytest.mark.typst


def spec() -> BookSpec:
    return BookSpec.model_validate(
        {
            "book": {"title": "Vault Book", "audience": "adult", "content_pages": 4, "seed": 3},
            "puzzles": {"mode": "mixed", "types": [{"type": "sudoku"}, {"type": "maze"}]},
            "back_matter": ["solutions", "case_vault"],
        }
    )


def test_case_vault_page_passes_whole_qa(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_DOMAIN", "casevault.example.com")
    out = build_book(spec(), tmp_path / "o", tmp_path / "f.db")
    report = run_gate(out, tmp_path / "f.db")
    failed = [(c.id, c.message) for c in report.checks if c.status == "fail"]
    assert report.result == "PASSED", failed
    by_id = {c.id: c for c in report.checks}
    assert by_id["L4.vault_page"].status == "pass"
    lay = json.loads((out / "layout.json").read_text())
    img = next(b for p in lay["pages"] for b in p["blocks"] if b.get("kind") == "image")
    assert img["url"] == f"https://casevault.example.com/solve/{report.book_id}"
    # tampering with the URL is caught
    for p in lay["pages"]:
        for b in p["blocks"]:
            if b.get("kind") == "image":
                b["url"] = "https://evil.example/solve/x"
    (out / "layout.json").write_text(json.dumps(lay))
    r = run_one(REGISTRY["L4.vault_page"], BookContext(out, tmp_path / "f.db"))
    assert r.status == "fail" and "does not open" in r.message


def test_case_vault_needs_domain(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_DOMAIN", "")
    with pytest.raises(ValueError, match="VAULT_DOMAIN"):
        build_book(spec(), tmp_path / "o", tmp_path / "f.db")
