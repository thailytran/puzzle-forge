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


def test_theme_from_design_kit(tmp_path: Path) -> None:
    from forge.mystery.art import build_theme, theme_margins

    assert build_theme({}, 8.5, 11, 6.5) == ({}, None)
    frame = _png(tmp_path / "frame.png", 900, 1200)
    sign = Image.new("RGB", (1600, 900), (255, 255, 255))
    sign.paste((150, 90, 40), (100, 350, 1500, 550))  # the wooden plank on white
    sign.save(tmp_path / "plaque.png")
    files, theme = build_theme(
        {"design:frame": frame, "design:plaque": tmp_path / "plaque.png"}, 8.5, 11, 6.0
    )
    assert theme is not None and theme["background"] == "theme/frame.jpg"
    assert set(files) == {"theme/frame.jpg", "theme/plaque.png", "theme/frame_overlay.png"}
    plaque = Image.open(__import__("io").BytesIO(files["theme/plaque.png"]))
    assert plaque.mode == "RGBA" and plaque.width / plaque.height > 5  # cropped to the plank
    assert plaque.getpixel((0, 0))[3] == 0 or plaque.getpixel((plaque.width // 2, 1))[3] == 255
    m = theme_margins(8.5, 11)
    assert m["inside"] >= 0.8 and m["top"] >= 1.0 and m["bottom"] >= 1.2


def test_split_icons_reading_order(tmp_path: Path) -> None:
    from forge.mystery.art import split_icons

    sheet = Image.new("RGB", (1200, 600), (255, 255, 255))
    for i in range(8):
        x, y = 60 + (i % 4) * 290, 80 + (i // 4) * 280
        sheet.paste((20 + i * 25, 80, 160), (x, y, x + 150 + i * 5, y + 150))
    sheet.save(tmp_path / "icons.png")
    out = split_icons(tmp_path / "icons.png")
    assert len(out) == 8
    first = Image.open(__import__("io").BytesIO(out[0]))
    assert first.mode == "RGBA" and first.getpixel((first.width // 2, first.height // 2))[0] == 20


def test_find_panel_and_templates(tmp_path: Path) -> None:
    from forge.mystery.art import PANEL_RGB, build_templates, find_panel

    page = Image.new("RGB", (900, 1200), (150, 40, 40))  # colourful designed page
    page.paste(PANEL_RGB, (100, 300, 800, 1000))  # the empty puzzle panel
    page.paste((240, 200, 60), (120, 1050, 780, 1150))  # a tips box below
    page.save(tmp_path / "tpl.png")
    x0, _y0, _x1, y1 = find_panel(tmp_path / "tpl.png") or (0, 0, 0, 0)
    assert abs(x0 - 100 / 900) < 0.03 and abs(y1 - 1000 / 1200) < 0.03
    files, tpls = build_templates({"design:tpl_maze": tmp_path / "tpl.png"}, 8.5, 11)
    assert "theme/tpl_maze.jpg" in files and 5.5 < tpls["maze"]["w_in"] < 6.7
    assert find_panel(_png(tmp_path / "plain.png", 300, 400)) is None


def test_long_story_is_split_between_paragraphs() -> None:
    from forge.mystery.art import STORY_WORDS, split_story

    short = [{"kind": "paragraph", "text": "word " * 40}]
    assert split_story(short) == (short, [])
    long = [{"kind": "paragraph", "text": "word " * 60} for _ in range(5)]
    head, tail = split_story(long)
    assert head + tail == long and head and tail
    assert abs(len(head) - len(tail)) <= 1
    assert sum(len(b["text"].split()) for b in long) > STORY_WORDS
