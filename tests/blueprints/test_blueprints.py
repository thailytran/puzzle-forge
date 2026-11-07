from __future__ import annotations

from pathlib import Path

import pytest

from forge.blueprints import PAGE_TYPES, Zone, blueprint_lines, load_blueprint, validate_blueprint


def test_escape_adult_valid_and_complete() -> None:
    bp = load_blueprint("escape_adult")
    assert validate_blueprint(bp) == []
    assert set(PAGE_TYPES) <= set(bp.page_types)
    assert set(bp.page_types["main_puzzle"].variants) == {"art_top", "art_side", "frame"}
    assert bp.page_types["cutout"].single_sided
    assert "escape_adult" in blueprint_lines()


def test_zones_sorted_by_z_and_knockout() -> None:
    bp = load_blueprint("escape_adult")
    zs = bp.zones("main_puzzle", "art_top")
    assert [z.z for z in zs] == sorted(z.z for z in zs)
    assert {z.kind for z in bp.knockout("main_puzzle", "art_top")} == {"text", "puzzle", "input"}


def test_scaling_to_a4() -> None:
    bp = load_blueprint("escape_adult")
    a = bp.zones("story", "full_text")[-1]
    b = bp.zones("story", "full_text", trim="A4")[-1]
    assert b.w == pytest.approx(a.w * 8.27 / 8.5)


def test_validator_catches_overlap_and_binding() -> None:
    bp = load_blueprint("escape_adult")
    bad = bp.model_copy(deep=True)
    zones = bad.page_types["reference"].variants["default"]
    zones.append(Zone(name="extra", kind="puzzle", x=5, y=20, w=50, h=50, z=10))
    problems = validate_blueprint(bad)
    assert any("binding margin" in p for p in problems)
    assert any("overlap" in p for p in problems)


@pytest.mark.typst
def test_preview_pdf(tmp_path: Path) -> None:
    from pypdf import PdfReader

    from forge.blueprints.preview import render_preview

    bp = load_blueprint("escape_adult")
    pdf = render_preview(bp, tmp_path / "p.pdf")
    n_variants = sum(len(pt.variants) for pt in bp.page_types.values())
    assert len(PdfReader(pdf).pages) == n_variants + 1
