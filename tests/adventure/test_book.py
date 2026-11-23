"""Adventure pages, layout and Studio contract (ROADMAP P9.2-P9.4)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from forge.adventure import pages as pg
from forge.adventure.book import (
    STORY_STYLE,
    art_keys,
    build_adventure_book,
    layout_book,
    paragraphs,
    spread_ok,
)
from forge.adventure.frame import AdventureFrame, build_puzzles, load_frame
from forge.adventure.studio import merge_writing, studio_package, writing_brief
from forge.layout.document import Page

FRAME = Path(__file__).resolve().parents[2] / "configs/adventures/snow_queens_library.json"


@pytest.fixture(scope="module")
def frame() -> AdventureFrame:
    return load_frame(FRAME)


@pytest.fixture(scope="module")
def laid(frame: AdventureFrame):  # type: ignore[no-untyped-def]
    return layout_book(frame, build_puzzles(frame, 3), {})


def _img(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_story_pages_are_left_pages_facing_their_search(laid) -> None:  # type: ignore[no-untyped-def]
    bk, _ = laid
    assert spread_ok(bk.pages) == []
    for i, p in enumerate(bk.pages):
        if (p.style or {}).get("type") == STORY_STYLE and p.title.startswith("Chapter"):
            assert (i + 1) % 2 == 0
            assert bk.pages[i + 1].title.endswith("Search")


def test_every_chapter_has_six_pages_and_48_in_total(laid) -> None:  # type: ignore[no-untyped-def]
    bk, _ = laid
    assert bk.chapter_pages == 48


def test_spread_check_catches_a_right_hand_story() -> None:
    p = Page(kind="text", title="x", style={"type": STORY_STYLE})
    assert spread_ok([p]) and not spread_ok([Page(kind="text"), p])


def test_art_requests_cover_every_chapter(laid, frame: AdventureFrame) -> None:  # type: ignore[no-untyped-def]
    bk, _ = laid
    keys = {r["id"] for r in bk.requests}
    for ch in frame.chapters:
        assert {f"vignette:ch{ch.no}", f"search:ch{ch.no}", f"icons:ch{ch.no}"} <= keys
    search = next(r for r in bk.requests if r["id"] == "search:ch1")
    assert search["objects"][0] == "teacup" and "JSON" in search["brief"]
    assert any(r["id"] == "char:plume" for r in bk.requests)


def test_paragraphs_keep_quotes_together(frame: AdventureFrame) -> None:
    for para in paragraphs(frame.prologue):
        assert para.count('"') % 2 == 0
    assert 4 <= len(paragraphs(frame.prologue)) <= 7


def test_page_pictures_have_print_size() -> None:
    im = _img(pg.search_page(1, ["teacup", "quill"] * 6, None))
    assert im.size == (2550, 3300)
    im = _img(pg.story_page("Chapter 1 | Test", None))
    assert im.size == (2550, 3300)
    # the bottom band stays white for the page number
    band = im.crop((0, 3300 - 135, 2550, 3300)).convert("L")
    assert band.getextrema() == (255, 255)


def _scene(tmp: Path) -> Path:
    im = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(im).ellipse([100, 100, 200, 200], outline="black", width=6)
    f = tmp / "search_ch1.png"
    im.save(f)
    return f


def test_split_icon_sheet_keeps_list_order(tmp_path: Path) -> None:
    sheet = Image.new("RGB", (800, 400), "white")
    d = ImageDraw.Draw(sheet)
    d.ellipse([50, 50, 150, 150], outline="black", width=8)  # cell 1: circle
    d.rectangle([250, 40, 350, 160], outline="black", width=8)  # cell 2: tall box
    # cell 3 left empty
    d.line([(650, 50), (750, 150)], fill="black", width=8)  # cell 4: line
    d.rectangle([20, 230, 380, 370], outline="black", width=8)  # cell 5: wide box
    f = tmp_path / "icons.png"
    sheet.save(f)
    icons = pg.split_icon_sheet(f, 5, cols=4)
    assert len(icons) == 5 and icons[2] == b""
    w1, h1 = _img(icons[1]).size
    w4, h4 = _img(icons[4]).size
    assert h1 > w1 and w4 > h4  # the tall box and the wide box stayed in their cells
    assert _img(icons[0]).mode == "RGBA"


def test_answer_key_draws_rings_only_where_marked(tmp_path: Path) -> None:
    scene = _scene(tmp_path)
    plain = _img(pg.answer_key(1, ["teacup"], scene, [], (3.0, 4.0)))
    ringed = _img(
        pg.answer_key(
            1, ["teacup"], scene, [{"name": "teacup", "x": 0.5, "y": 0.5, "r": 0.05}], (3.0, 4.0)
        )
    )
    centre = (
        plain.width // 2 - 60,
        plain.height // 2 - 60,
        plain.width // 2 + 60,
        plain.height // 2 + 60,
    )
    assert plain.crop(centre).convert("L").getextrema()[0] == 255
    assert ringed.crop(centre).convert("L").getextrema()[0] < 80


def test_build_reports_owner_ticks(frame: AdventureFrame, tmp_path: Path) -> None:
    art = tmp_path / "art"
    art.mkdir()
    _scene(art)
    names = [o for o in frame.chapters[0].hidden_objects]
    (art / "selfcheck.json").write_text(
        json.dumps({"ch1": [{"name": n, "x": 0.1, "y": 0.1, "r": 0.03} for n in names]})
    )
    (art / "review.json").write_text(json.dumps({"ch1": {n: True for n in names[1:]}}))
    man = build_adventure_book(frame, tmp_path / "out", seed=3, render=False, art_dir=art)
    st = man["search_check"]["ch1"]
    assert st["marked"] == 12 and st["ticked"] == 11 and st["not_ticked"] == [names[0]]
    assert not st["ok"] and not man["ready_for_review"]
    assert "search:ch1" in man["art"]["used"] and "search:ch2" in man["art"]["missing"]
    assert man["content_pages"] == 48 and man["reader_sim"]["ok"]
    assert (tmp_path / "out" / "pages" / "search_ch1.png").is_file()
    assert "EVERGLOW" not in (tmp_path / "out" / "manifest.json").read_text()


def test_art_keys_from_windows_file_names() -> None:
    keys = art_keys({"search_ch1": Path("a.png"), "cover": Path("c.png")})
    assert keys["search:ch1"] == Path("a.png") and "cover" in keys
    studio = art_keys({"find:ch2": Path("f.png"), "ch2": Path("v.png"), "find_ch3": Path("g.png")})
    assert studio["search:ch2"] == Path("f.png") and studio["vignette:ch2"] == Path("v.png")
    assert studio["search:ch3"] == Path("g.png")


def test_writing_brief_forbids_answers(frame: AdventureFrame) -> None:
    b = writing_brief(frame)
    assert "EVERGLOW" in b["forbidden"] and "RAVEN" in b["forbidden"]
    assert len(b["return_json"]["chapters"]) == 8


def test_studio_package_keeps_owner_ticks(frame: AdventureFrame, tmp_path: Path) -> None:
    studio_package(frame, [], tmp_path)
    rv = tmp_path / "review.json"
    rv.write_text(json.dumps({"ch1": {"teacup": True}}))
    studio_package(frame, [], tmp_path)
    assert json.loads(rv.read_text()) == {"ch1": {"teacup": True}}


def test_merge_writing_cannot_change_answers(frame: AdventureFrame) -> None:
    ok, rep = merge_writing(
        frame,
        {
            "chapters": [
                {"no": 1, "teaser": "Up the stair you go.", "puzzle_a": {"answer": "ROBIN"}}
            ]
        },
    )
    assert rep.ok and ok.chapters[0].teaser and ok.chapters[0].puzzle_a.answer == "RAVEN"
    _bad, rep = merge_writing(frame, {"chapters": [{"no": 1, "story": "A raven sings."}]})
    assert not rep.ok and any("leak" in p for p in rep.problems)
    _, rep = merge_writing(frame, {"listing": {"blurb": "Find the word EVERGLOW!"}})
    assert not rep.ok
