from __future__ import annotations

import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from forge.layout.demo import demo_layout
from forge.layout.document import Page, make_layout, pad_pages, render_pdf, write_build_dir
from forge.layout.trim import TRIMS


def test_pad_pages_even() -> None:
    pages = pad_pages([Page(kind="text")] * 3, min_pages=0)
    assert len(pages) == 4
    assert pages[-1].kind == "notes"


def test_make_layout_unknown_trim() -> None:
    with pytest.raises(ValueError):
        make_layout(title="x", trim="5x5", pages=[])


def test_demo_layout_even_and_margins() -> None:
    doc = demo_layout("6x9")
    assert len(doc.pages) % 2 == 0
    assert doc.width_in == 6.0
    assert doc.margins["inside"] >= 0.375


def test_build_dir(tmp_path: Path) -> None:
    main = write_build_dir(demo_layout(), tmp_path, files={"img/a.svg": b"<svg/>"})
    assert main.name == "book.typ"
    assert json.loads((tmp_path / "layout.json").read_text())["title"]
    assert (tmp_path / "img" / "a.svg").read_bytes() == b"<svg/>"


def _font_names(reader: PdfReader) -> set[str]:
    names: set[str] = set()
    for page in reader.pages:
        fonts = page["/Resources"].get("/Font", {})
        for ref in fonts.values():
            f = ref.get_object()
            names.add(str(f.get("/BaseFont")))
    return names


@pytest.mark.typst
@pytest.mark.parametrize("trim", sorted(TRIMS))
def test_render_demo_pdf(tmp_path: Path, trim: str) -> None:
    doc = demo_layout(trim)
    pdf = render_pdf(doc, tmp_path / "interior.pdf")
    reader = PdfReader(pdf)
    assert len(reader.pages) == len(doc.pages)
    assert len(reader.pages) % 2 == 0
    box = reader.pages[0].mediabox
    assert abs(float(box.width) - TRIMS[trim].width_in * 72) < 0.5
    assert abs(float(box.height) - TRIMS[trim].height_in * 72) < 0.5
    fonts = " ".join(_font_names(reader))
    assert "AtkinsonHyperlegible" in fonts
    assert "Libertinus" in fonts


@pytest.mark.typst
def test_render_is_deterministic(tmp_path: Path) -> None:
    a = render_pdf(demo_layout(), tmp_path / "a" / "interior.pdf").read_bytes()
    b = render_pdf(demo_layout(), tmp_path / "b" / "interior.pdf").read_bytes()
    assert a == b
