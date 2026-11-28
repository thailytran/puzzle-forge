from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from forge.book.builder import build_book
from forge.core.book import BookSpec
from forge.editions.build import build_edition
from forge.editions.settings import EditionSettings
from forge.editions.stamp import (
    Order,
    decode_bits,
    encode_bits,
    stamp_book,
    trace_pdf,
    verify_stamp,
)
from forge.qa.gate import run_gate


@pytest.mark.parametrize("order", [0, 1, 1234, 987654321, 2**32 - 1])
def test_bits_roundtrip(order: int) -> None:
    assert decode_bits(encode_bits(order)) == order


def test_checksum_rejects_corruption() -> None:
    bits = encode_bits(1234)
    bits[5] ^= 1
    assert decode_bits(bits) != 1234


@pytest.fixture(scope="module")
def master(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    tmp = tmp_path_factory.mktemp("stamp")
    spec = BookSpec.model_validate(
        {
            "book": {"title": "Stamp Book", "audience": "adult", "content_pages": 4, "seed": 5},
            "puzzles": {"mode": "mixed", "types": [{"type": "sudoku"}, {"type": "maze"}]},
        }
    )
    out = build_book(spec, tmp / "o", tmp / "f.db")
    pdf = build_edition(out, EditionSettings(name="digital"))
    return out, pdf


@pytest.mark.typst
def test_stamp_requires_qa(master: tuple[Path, Path]) -> None:
    out, _ = master
    with pytest.raises(PermissionError):
        stamp_book(out, Order("Jane D.", 77))


@pytest.mark.typst
def test_stamp_verify_trace(master: tuple[Path, Path]) -> None:
    out, pdf = master
    assert run_gate(pdf.parent, out.parent.parent / "f.db").result == "PASSED"
    files = stamp_book(out, Order("Jane D.", 4242, "jane@example.com"))
    stamped = files[0]
    r = PdfReader(stamped)
    assert r.is_encrypted
    r.decrypt("")
    assert r.metadata["/ForgeOrder"] == "4242"
    assert "Licensed to Jane D." in r.pages[0].extract_text()
    t = trace_pdf(stamped)
    assert t["metadata_order"] == "4242" and t["pattern_order"] == 4242
    assert verify_stamp(pdf, stamped) == []


@pytest.mark.typst
def test_verify_detects_change_outside_band(master: tuple[Path, Path], tmp_path: Path) -> None:
    _, pdf = master
    other = build_edition(master[0], EditionSettings(name="digital", trim="A4"))
    problems = verify_stamp(pdf, other)
    assert problems  # different page content/size => rejected
