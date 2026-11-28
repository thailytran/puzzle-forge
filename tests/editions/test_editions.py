from __future__ import annotations

from pathlib import Path

import pytest

from forge.book.builder import build_book
from forge.core.book import BookSpec
from forge.editions.brand import load_brand, recolor_svg, tint, to_gray
from forge.editions.build import build_edition
from forge.editions.settings import EditionSettings
from forge.qa.gate import run_gate


def test_tint_and_gray() -> None:
    assert tint("#000000", 0.05) == "#f2f2f2"
    assert tint("#1F4E79", 0.0) == "#ffffff"
    assert to_gray("#ffffff") == "#ffffff"
    assert recolor_svg('<p fill="#1F4E79"/><c fill="#ffffff"/>', "#abcdef") == (
        '<p fill="#abcdef"/><c fill="#ffffff"/>'
    )
    assert load_brand().microtext.startswith("© 2026 ")


def test_edition_margins() -> None:
    kdp = {"inside": 0.5, "outside": 0.5, "top": 0.5, "bottom": 0.5}
    assert EditionSettings(name="spiral").margins(kdp)["inside"] == 0.75
    assert EditionSettings(name="spiral", binding="wire-o").margins(kdp)["inside"] == 0.625
    assert EditionSettings(name="kdp").margins(kdp) == kdp


@pytest.mark.typst
@pytest.mark.parametrize(
    "ed",
    [
        EditionSettings(name="digital", trim="A4"),
        EditionSettings(name="spiral", color=False, duplex=False, bleed=True, crop_marks=True),
    ],
    ids=["digital-A4", "spiral-gray-simplex-bleed"],
)
def test_edition_builds_and_passes_qa(tmp_path: Path, ed: EditionSettings) -> None:
    spec = BookSpec.model_validate(
        {
            "book": {"title": "Edition Book", "audience": "adult", "content_pages": 6, "seed": 8},
            "puzzles": {
                "mode": "mixed",
                "types": [{"type": "wordsearch"}, {"type": "sudoku"}, {"type": "maze"}],
            },
        }
    )
    out = build_book(spec, tmp_path / "o", tmp_path / "f.db")
    pdf = build_edition(out, ed)
    assert (pdf.parent / "interior_nowm.pdf").is_file()
    r = run_gate(pdf.parent, tmp_path / "f.db", layers={"L1", "L2"})
    failed = [(c.id, c.message) for c in r.checks if c.status == "fail"]
    assert r.result == "PASSED", failed
    ran = {c.id for c in r.checks if c.status == "pass"}
    assert {"L2.watermark_knockout", "L2.watermark_contrast"} <= ran
    if ed.name == "spiral":
        assert {"L2.binding_margin", "L2.bleed_marks"} <= ran
