from __future__ import annotations

import re
from pathlib import Path

import pytest

from forge.book.builder import build_book
from forge.core.book import BookSpec
from forge.qa.gate import run_gate
from forge.qa.review_pack import make_review


@pytest.mark.typst
def test_review_pack(tmp_path: Path) -> None:
    spec = BookSpec.model_validate(
        {
            "book": {"title": "Pack Book", "audience": "kids_6_8", "content_pages": 6, "seed": 2},
            "puzzles": {
                "mode": "progressive",
                "distribution": {"very_easy": 1, "easy": 1, "medium": 1},
                "types": [{"type": "wordsearch"}, {"type": "maze"}],
            },
        }
    )
    out = build_book(spec, tmp_path / "o", tmp_path / "f.db")
    run_gate(out, tmp_path / "f.db")
    md = make_review("PX", [out], tmp_path / "review")
    text = md.read_text()
    assert "# Review PX" in text and "Pack Book" in text and "- [ ] p.1 — title page" in text
    assert "Kids 6-8" in text and "PASSED" in text
    book_dir = tmp_path / "review" / "PX" / out.name
    assert (book_dir / "interior.pdf").is_file() and (book_dir / "page-001.png").is_file()
    links = re.findall(r"\]\((PX/[^)]+)\)", text)
    assert len(links) >= 4
    for target in links:
        assert (tmp_path / "review" / target).is_file(), target
