"""P8.3g: Studio art placed in a CBN Mystery book (forge/mystery/art.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from forge.mystery.art import PORTRAITS_TITLE, key_of, load_art, place_art


@dataclass
class P:
    kind: str
    title: str | None = None
    blocks: list[dict[str, Any]] = field(default_factory=list)


def _png(path: Path, w: int, h: int) -> Path:
    Image.new("RGB", (w, h), (200, 120, 60)).save(path)
    return path


def _book() -> tuple[list[P], list[dict[str, Any]]]:
    pages = [
        P("title"),
        P("text", "How To Play"),
        P("text", "Prologue", [{"kind": "paragraph", "text": "x"}]),
        P("text", "The Suspects"),
        P("text", "Chapter 1", [{"kind": "paragraph", "text": "y"}]),
    ]
    reqs = [
        {"page": 0, "zone": "character_sheet", "id": "char:wren"},
        {"page": 1, "zone": "cover_art", "id": "cover"},
        {"page": 3, "zone": "scene", "id": "prologue"},
        {"page": 4, "zone": "portraits", "id": "portraits"},
        {"page": 5, "zone": "scene", "id": "ch1"},
    ]
    return pages, reqs


def test_key_of() -> None:
    assert key_of("char_wren") == "char:wren"
    assert key_of("loc_fir") == "loc:fir"
    assert key_of("ch3") == "ch3"


def test_load_art_manifest_and_names(tmp_path: Path) -> None:
    _png(tmp_path / "cover.png", 30, 40)
    _png(tmp_path / "char_wren.png", 30, 20)
    _png(tmp_path / "other.png", 30, 20)
    (tmp_path / "art_manifest.json").write_text(json.dumps({"prologue": {"file": "other.png"}}))
    art = load_art(tmp_path)
    assert art["cover"].name == "cover.png"
    assert art["char:wren"].name == "char_wren.png"
    assert art["prologue"].name == "other.png"


def test_place_art_puts_pictures_on_their_pages(tmp_path: Path) -> None:
    pages, reqs = _book()
    art = {
        "cover": _png(tmp_path / "cover.png", 1500, 2000),
        "prologue": _png(tmp_path / "prologue.png", 2400, 1800),
        "portraits": _png(tmp_path / "portraits.png", 2430, 2730),
        "ch1": _png(tmp_path / "ch1.png", 2400, 1800),
        "char:wren": _png(tmp_path / "w.png", 300, 200),
    }
    files, rep = place_art(pages, reqs, art, 6.5, 9.0, P)
    assert rep["missing"] == [] and rep["pages_added"] == 1
    assert sorted(rep["placed"]) == ["ch1", "cover", "portraits", "prologue"]
    assert "art/char_wren.jpg" not in files  # reference sheets are never printed
    assert pages[0].blocks[0]["path"] == "art/cover.jpg"
    assert pages[2].blocks[0]["kind"] == "image" and pages[2].blocks[2]["text"] == "x"
    assert pages[4].title == PORTRAITS_TITLE and pages[3].title == "The Suspects"
    assert pages[5].blocks[0]["path"] == "art/ch1.jpg"
    for name, data in files.items():
        im = Image.open(__import__("io").BytesIO(data))
        assert im.format == "JPEG"
        w_in = next(b["width_in"] for p in pages for b in p.blocks if b.get("path") == name)
        assert im.width <= round(w_in * 300) + 1  # 300 dpi at the printed size, not the 2K original


def test_portraits_fit_the_page_height(tmp_path: Path) -> None:
    pages, reqs = _book()
    art = {"portraits": _png(tmp_path / "p.png", 1000, 2000)}  # very tall
    place_art(pages, reqs, art, 6.5, 9.0, P)
    blk = pages[4].blocks[0]
    assert blk["width_in"] * 2 <= 9.0 * 0.92 + 0.01


def test_missing_art_is_reported_not_fatal(tmp_path: Path) -> None:
    pages, reqs = _book()
    files, rep = place_art(pages, reqs, {"cover": _png(tmp_path / "c.png", 300, 400)}, 6.5, 9.0, P)
    assert rep["placed"] == ["cover"]
    assert set(rep["missing"]) == {"prologue", "portraits", "ch1"}
    assert len(pages) == 5 and files.keys() == {"art/cover.jpg"}
