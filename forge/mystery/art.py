"""Put the Studio art (Gemini pictures) into a CBN Mystery book (P8.3g).

HALOSPARK Studio draws the art requests of `layout_pages` (cover, opening scene, chapter scenes) and
composes the suspect portraits in code; it hands over a folder `art/` with `<key>.png` files and an
`art_manifest.json` (key -> {file, zone, ...}). Keys: ``cover``, ``prologue``, ``portraits``,
``ch1`` ... ``chN``; reference sheets (``char:<id>``, ``loc:<id>``) are never printed.

Art never carries information the reader needs, so a missing picture only leaves its zone empty;
the build reports which ones are missing. Pictures are re-encoded as 300 dpi JPEG at the printed
size, so the PDF stays small.

Pure module (Pillow only): `forge.mystery.cbn_case.build_case_book` calls `place_art`.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

# printed width as a share of the text width; None = reference sheet, never printed
ZONE_WIDTH: dict[str, float | None] = {
    "cover_art": 0.78,
    "scene": 0.92,
    "portraits": 1.0,
    "character_sheet": None,
    "location_sheet": None,
}
# printed height cap as a share of the text height (scene pages keep room for the story)
MAX_HEIGHT: dict[str, float] = {"cover_art": 0.68, "scene": 0.46, "portraits": 0.92}
DPI = 300
PORTRAITS_TITLE = "Faces of the Case"


def key_of(stem: str) -> str:
    """File stem -> art key (``char_wren`` -> ``char:wren``, ``loc_fir`` -> ``loc:fir``)."""
    for pre in ("char_", "loc_"):
        if stem.startswith(pre):
            return pre[:-1] + ":" + stem[len(pre) :]
    return stem


def load_art(art_dir: Path) -> dict[str, Path]:
    """Key -> picture file. The manifest wins; other ``*.png`` / ``*.jpg`` files count by name."""
    art_dir = Path(art_dir)
    found: dict[str, Path] = {}
    for f in sorted(art_dir.glob("*")):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            found[key_of(f.stem)] = f
    man = art_dir / "art_manifest.json"
    if man.is_file():
        for key, rec in json.loads(man.read_text(encoding="utf-8")).items():
            f = art_dir / str((rec or {}).get("file") or "")
            if f.is_file():
                found[key] = f
    return found


def request_key(req: dict[str, Any]) -> str:
    return str(req.get("id") or f"{req.get('zone')}@{req.get('page')}")


def print_jpeg(src: Path, width_in: float) -> tuple[bytes, float]:
    """Re-encode at 300 dpi for the printed width; returns (jpeg bytes, printed height in in)."""
    from PIL import Image

    with Image.open(src) as im:
        rgb = im.convert("RGB")
    px = max(1, round(width_in * DPI))
    if rgb.width > px:
        rgb = rgb.resize((px, max(1, round(rgb.height * px / rgb.width))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=90, optimize=True, dpi=(DPI, DPI))
    return buf.getvalue(), width_in * rgb.height / rgb.width


# Owner 2026-11-21: a story page = the WHOLE picture in the top 50-55% of the frame opening and
# the story on plain paper under it. Nothing is ever laid over the picture (a picture may hold a
# clue) and no text is printed on it. A story longer than STORY_WORDS is split over two pictures
# (`story:<key>` and `story:<key>_2`).
STORY_PIC_MAX = 0.62  # tallest picture, as a share of the frame opening (owner: 60-65 %)
STORY_LEGACY_CROP = 0.58  # portrait pictures of the first draft: painted part = their top 58%
STORY_WORDS = 130  # words that fit the plain part under a 62 % picture


def split_story(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(first half, second half) cut between paragraphs near the middle; ([all], []) if short."""
    words = [len(str(b.get("text", "")).split()) for b in blocks]
    total = sum(words)
    if total <= STORY_WORDS or len(blocks) < 2:
        return blocks, []
    cut = min(range(1, len(blocks)), key=lambda i: abs(sum(words[:i]) - total / 2))
    return blocks[:cut], blocks[cut:]


STORY_FADE = 0.04  # width of the soft edge on the sides, as a share of the picture width
STORY_FADE_BOTTOM = 0.17  # height of the soft bottom edge, as a share of the picture height
STORY_PAPER = (251, 246, 240)  # the paper colour the picture melts into


def _soften(rgb: Any) -> Any:
    """Melt the picture's outer rim into the paper: no hard edge on any side, and a long gentle
    fade at the bottom where the story text starts. The pictures are painted with their important
    objects away from the edges, so only the rim is softened."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    w, h = rgb.size
    r = max(2.0, w * STORY_FADE / 2.2)
    inset = round(r * 1.9)
    side = Image.new("L", (w, h), 0)
    ImageDraw.Draw(side).rectangle(
        (inset, -h, w - inset - 1, h - inset - 1), fill=255
    )  # top left sharp: the frame hides it
    side = side.filter(ImageFilter.GaussianBlur(r))
    side = side.point(lambda v: round(255 * min(1.0, (v / 255) * 1.15)))
    fh = max(2, round(h * STORY_FADE_BOTTOM))
    ramp = Image.new("L", (w, h), 255)
    col = Image.new("L", (1, fh))
    col.putdata(
        [round(255 * (1 - (3 * t * t - 2 * t**3))) for t in (i / (fh - 1) for i in range(fh))]
    )
    ramp.paste(col.resize((w, fh)), (0, h - fh))
    mask = ImageChops.multiply(side, ramp)
    return Image.composite(rgb, Image.new("RGB", (w, h), STORY_PAPER), mask)


def story_jpeg(src: Path, box_w_in: float, box_h_in: float) -> tuple[bytes, float, float]:
    """The picture, complete and untouched, sized to fit the picture area of a story page, with soft
    edges that melt into the paper (the story text starts under it).

    Returns (jpeg, width, height) with the size as shares of the frame opening; the height never
    exceeds STORY_PIC_MAX."""
    from PIL import Image

    with Image.open(src) as im:
        rgb = im.convert("RGB")
    if rgb.height > rgb.width:  # first-draft portrait page: keep its painted top part only
        rgb = rgb.crop((0, 0, rgb.width, round(rgb.height * STORY_LEGACY_CROP)))
    ratio = rgb.width / rgb.height
    max_h = box_h_in * STORY_PIC_MAX
    w_in = min(box_w_in, max_h * ratio)
    px = round(w_in * 220)
    if rgb.width > px:
        rgb = rgb.resize((px, round(px * rgb.height / rgb.width)), Image.Resampling.LANCZOS)
    rgb = _soften(rgb)
    h_in = w_in * rgb.height / rgb.width
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=92, optimize=True, dpi=(220, 220))
    return buf.getvalue(), round(w_in / box_w_in, 4), round(h_in / box_h_in, 4)


BANNER_RATIO = 2.7  # width / height of the picture strip on text-only pages
# owner 2026-11-21: no page may be only text + frame -> these pages get a picture strip
# (a crop of an existing scene) under their title: page title prefix -> art key
BANNER_PAGES: tuple[tuple[str, str | None], ...] = (
    ("Code Log", "prologue"),
    ("Final Deduction", "cover"),
    ("Hints", "prologue"),
    ("Case Closed", "cover"),
)


def banner_jpeg(src: Path, width_in: float) -> tuple[bytes, float]:
    """A wide strip cut from the middle of a picture, rim softened -> (jpeg, height in in)."""
    from PIL import Image

    with Image.open(src) as im:
        rgb = im.convert("RGB")
    h = min(rgb.height, round(rgb.width / BANNER_RATIO))
    top = round((rgb.height - h) * 0.45)
    rgb = rgb.crop((0, top, rgb.width, top + h))
    px = round(width_in * 200)
    if rgb.width > px:
        rgb = rgb.resize((px, round(px * rgb.height / rgb.width)), Image.Resampling.LANCZOS)
    rgb = _soften(rgb)
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=90, optimize=True, dpi=(200, 200))
    return buf.getvalue(), width_in * rgb.height / rgb.width


def decorate_plain_pages(
    pages: list[Any], art: dict[str, Path], text_width_in: float
) -> dict[str, bytes]:
    """A picture strip at the top of every page that would be only text on the frame."""
    files: dict[str, bytes] = {}
    width = round(text_width_in * 0.9, 2)
    for i, page in enumerate(pages):
        if getattr(page, "style", None) is not None or getattr(page, "kind", "") != "text":
            continue
        title = str(getattr(page, "title", "") or "")
        key = None
        m = re.match(r"Evidence Card (\d+)", title)
        key = f"ch{m.group(1)}" if m else next((k for pre, k in BANNER_PAGES if pre in title), None)
        src = art.get(key) if key else None
        if src is None or any(b.get("kind") == "image" for b in page.blocks):
            continue
        name = f"art/banner_{i + 1}.jpg"
        files[name], _h = banner_jpeg(src, width)
        page.blocks[:0] = [
            {"kind": "image", "path": name, "width_in": width},
            {"kind": "spacer", "height_in": 0.12},
        ]
    return files


def page_jpeg(src: Path, width_in: float, height_in: float) -> bytes:
    """A designed full page (poster) at print size."""
    from PIL import Image

    with Image.open(src) as im:
        rgb = im.convert("RGB").resize(
            (round(width_in * 200), round(height_in * 200)), Image.Resampling.LANCZOS
        )
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=88, optimize=True, dpi=(200, 200))
    return buf.getvalue()


def place_poster(
    pages: list[Any], art: dict[str, Path], key: str, title: str, page_in: tuple[float, float]
) -> dict[str, bytes]:
    """`key` (e.g. `design:howto`) is a whole page designed with its text: it replaces the text
    page called `title`. The owner proof-reads such a page in the Studio before approving."""
    src = art.get(key)
    page = next((p for p in pages if getattr(p, "title", None) == title), None)
    if src is None or page is None:
        return {}
    name = f"theme/{key.split(':', 1)[-1]}.jpg"
    page.style = {"type": "poster", "bg": name}
    page.blocks = []
    return {name: page_jpeg(src, *page_in)}


def place_art(
    pages: list[Any],
    requests: list[dict[str, Any]],
    art: dict[str, Path],
    text_width_in: float,
    text_height_in: float,
    make_page: Callable[..., Any],
    page_in: tuple[float, float] = (8.5, 11.0),
    window: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Insert an image block at the top of each requested page (title page: under the title).

    `requests[i]["page"]` is the 1-based page number from `layout_pages`. Portraits go on their
    own page right after the suspects page (the dossier list fills that page). Pages are any
    objects with a mutable ``blocks`` list; `make_page(kind=..., title=..., blocks=...)` builds the
    extra portraits page. Returns the files for the Typst build dir and a report."""
    files: dict[str, bytes] = {}
    placed: list[str] = []
    missing: list[str] = []
    inserts: list[tuple[int, Any]] = []
    for req in requests:
        share = ZONE_WIDTH.get(str(req.get("zone")), 0.64)
        if share is None:
            continue
        key = request_key(req)
        src = art.get(key)
        n = int(req.get("page") or 0)
        story = art.get(f"story:{key}")  # full-page storytelling picture (owner 2026-11-21)
        if story is not None and 1 <= n <= len(pages):
            name = f"art/story_{key}.jpg"
            box = (page_in[0] * window[2], page_in[1] * window[3])
            files[name], pw, ph = story_jpeg(story, *box)
            pages[n - 1].style = {"type": "story", "bg": name, "w": pw, "h": ph}
            placed.append(f"story:{key}")
            second = art.get(f"story:{key}_2")
            head, tail = split_story(pages[n - 1].blocks)
            if second is not None and tail:  # long story: two pictures, half the text under each
                name2 = f"art/story_{key}_2.jpg"
                files[name2], pw, ph = story_jpeg(second, *box)
                pages[n - 1].blocks = head
                more = make_page(kind="text", title=pages[n - 1].title, blocks=tail)
                more.style = {"type": "story", "bg": name2, "w": pw, "h": ph}
                inserts.append((n, more))
                placed.append(f"story:{key}_2")
            continue
        if src is None or not 1 <= n <= len(pages):
            missing.append(key)
            continue
        width = round(text_width_in * share, 2)
        data, height = print_jpeg(src, width)
        cap = text_height_in * MAX_HEIGHT.get(str(req.get("zone")), 0.42)
        if height > cap:  # tall pictures shrink so the page keeps its text / title
            width = round(width * cap / height, 2)
            data, height = print_jpeg(src, width)
        name = f"art/{key.replace(':', '_')}.jpg"
        files[name] = data
        block = {"kind": "image", "path": name, "width_in": width}
        if req.get("zone") == "portraits":  # same page as the suspects list: no picture-only page
            width = round(width * 0.85, 2)
            files[name], _h = print_jpeg(src, width)
            pages[n - 1].blocks.insert(0, {**block, "width_in": width})
            pages[n - 1].blocks.insert(1, {"kind": "spacer", "height_in": 0.1})
        else:
            pages[n - 1].blocks.insert(0, block)
            if req.get("zone") == "scene":
                pages[n - 1].blocks.insert(1, {"kind": "spacer", "height_in": 0.15})
        placed.append(key)
    for n, page in sorted(inserts, key=lambda x: -x[0]):
        pages.insert(n, page)
    files.update(decorate_plain_pages(pages, art, text_width_in))
    return files, {"placed": placed, "missing": missing, "pages_added": len(inserts)}


# ---------------------------------------------------------------- page theme (Studio design kit)
FRAME_SHARE = (
    0.125,
    0.105,
)  # frame border width / height as a share of the page (the centre is empty parchment)


def theme_margins(width_in: float, height_in: float) -> dict[str, float]:
    """Margins that keep text inside the empty centre of the page frame."""
    sx, sy = FRAME_SHARE
    side = round(max(0.75, width_in * sx), 2)
    return {
        "inside": side,
        "outside": side,
        "top": round(max(0.8, height_in * sy), 2),
        "bottom": round(max(1.15, height_in * 0.18), 2),  # corner ornaments (lantern, pine) sit low
    }


def _plaque_png(src: Path) -> tuple[bytes, float]:
    """Crop the sign out of its white background (made transparent) -> (png, w/h)."""
    from PIL import Image

    with Image.open(src) as im:
        rgb = im.convert("RGB")
    px = rgb.load()
    w, h = rgb.size
    near = [[min(px[x, y]) > 238 for x in range(0, w, 4)] for y in range(0, h, 4)]
    rows = [y for y, r in enumerate(near) if not all(r)]
    cols = [x for x in range(len(near[0])) if not all(near[y][x] for y in range(len(near)))]
    if not rows or not cols:
        box = (0, 0, w, h)
    else:
        box = (
            max(0, cols[0] * 4 - 4),
            max(0, rows[0] * 4 - 4),
            min(w, cols[-1] * 4 + 8),
            min(h, rows[-1] * 4 + 8),
        )
    sign = rgb.crop(box).convert("RGBA")
    data = [
        (r, g, b, 0) if min(r, g, b) > 238 else (r, g, b, 255) for (r, g, b, _a) in sign.getdata()
    ]
    sign.putdata(data)
    if sign.width > 1600:
        sign = sign.resize((1600, max(1, round(sign.height * 1600 / sign.width))))
    buf = io.BytesIO()
    sign.save(buf, "PNG", optimize=True)
    return buf.getvalue(), sign.width / max(sign.height, 1)


def build_theme(
    art: dict[str, Path], width_in: float, height_in: float, text_width_in: float
) -> tuple[dict[str, bytes], dict[str, Any] | None]:
    """Page frame (`design:frame`) + heading plaque (`design:plaque`) -> Typst theme + files.
    None when the Studio has not drawn the kit yet (the book keeps the plain layout)."""
    from PIL import Image

    frame, plaque = art.get("design:frame"), art.get("design:plaque")
    if frame is None:
        return {}, None
    files: dict[str, bytes] = {}
    with Image.open(frame) as im:
        bg = im.convert("RGB").resize(
            (round(width_in * 150), round(height_in * 150)), Image.Resampling.LANCZOS
        )
    buf = io.BytesIO()
    bg.save(buf, "JPEG", quality=88, optimize=True, dpi=(150, 150))
    files["theme/frame.jpg"] = buf.getvalue()
    theme: dict[str, Any] = {
        "background": "theme/frame.jpg",
        "heading_font": "Young Serif",
        "heading_ink": "#fff3d6",  # cream letters on the wooden sign
        "accent": "#b8862b",
        "panel_fill": "#fffdf6",
        "margins": theme_margins(width_in, height_in),
    }
    if plaque is not None:
        png, ratio = _plaque_png(plaque)
        files["theme/plaque.png"] = png
        w = round(min(text_width_in, 5.6), 2)
        theme.update(
            plaque="theme/plaque.png",
            plaque_w_in=w,
            plaque_h_in=round(max(0.75, min(w / ratio, 1.15)), 2),
        )
    files["theme/frame_overlay.png"] = frame_overlay(frame)
    theme["overlay"] = "theme/frame_overlay.png"
    window = frame_window(frame)
    theme["window"] = {
        "x": round(window[0], 4),
        "y": round(window[1], 4),
        "w": round(window[2] - window[0], 4),
        "h": round(window[3] - window[1], 4),
    }
    tpl_files, tpls = build_templates(art, width_in, height_in, window)
    files.update(tpl_files)
    if tpls:
        theme["templates"] = tpls
    icons = art.get("design:icons")
    if icons is not None:
        names = []
        for name, png in zip(ICON_ORDER, split_icons(icons), strict=False):
            files[f"theme/icon_{name}.png"] = png
            names.append(name)
        theme["icons"] = {n: f"theme/icon_{n}.png" for n in names}
    return files, theme


ICON_ORDER = ("lantern", "key", "padlock", "magnifier", "chest", "watch", "bulb", "map")


def split_icons(src: Path, n: int = len(ICON_ORDER)) -> list[bytes]:
    """Sticker sheet (icons on white, 2 rows of 4) -> transparent PNGs in reading order."""
    from PIL import Image

    with Image.open(src) as im:
        rgb = im.convert("RGB")
    w, h = rgb.size
    k = 300 / w
    sm = rgb.resize((300, max(1, round(h * k))))
    px = sm.load()
    sw, sh = sm.size
    corners = [px[0, 0], px[sw - 1, 0], px[0, sh - 1], px[sw - 1, sh - 1]]
    bg = tuple(
        sorted(c[i] for c in corners)[1] for i in range(3)
    )  # sheet background (white or light grey)

    def far(c: tuple[int, ...]) -> bool:
        return sum(abs(c[i] - bg[i]) for i in range(3)) > 30

    ink = [[far(px[x, y]) for x in range(sw)] for y in range(sh)]
    seen = [[False] * sw for _ in range(sh)]
    boxes = []
    for y in range(sh):
        for x in range(sw):
            if not ink[y][x] or seen[y][x]:
                continue
            stack, xs, ys = [(x, y)], [], []
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                xs.append(cx)
                ys.append(cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < sw and 0 <= ny < sh and ink[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(xs) > sw * sh * 0.004:
                boxes.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1, len(xs)))
    boxes = sorted(boxes, key=lambda b: -b[4])[:n]
    rows = sorted(boxes, key=lambda b: b[1])
    half = len(rows) // 2 or 1
    ordered = sorted(rows[:half], key=lambda b: b[0]) + sorted(rows[half:], key=lambda b: b[0])
    out = []
    for x0, y0, x1, y1, _ in ordered:
        pad = 3
        box = (
            max(0, round((x0 - pad) / k)),
            max(0, round((y0 - pad) / k)),
            min(w, round((x1 + pad) / k)),
            min(h, round((y1 + pad) / k)),
        )
        ic = rgb.crop(box).convert("RGBA")
        ic.putdata(
            [
                (r, g, b, 0) if not far((r, g, b)) else (r, g, b, 255)
                for (r, g, b, _a) in ic.getdata()
            ]
        )
        ic.thumbnail((360, 360))
        buf = io.BytesIO()
        ic.save(buf, "PNG", optimize=True)
        out.append(buf.getvalue())
    return out


# ---------------------------------------------------------------- Gemini-designed puzzle pages
# (owner 2026-11-20) Gemini designs the WHOLE page of each puzzle type (title, how-to-play, tips,
# slogan, ornaments, colours) and leaves one flat empty panel in PANEL_RGB; code finds that panel
# and places the exact, verified puzzle inside it.
PANEL_RGB = (255, 251, 240)  # "#FFFBF0" asked in the Studio prompt


def find_panel(src: Path) -> tuple[float, float, float, float] | None:
    """Largest flat area close to PANEL_RGB -> (x0, y0, x1, y1) as page fractions, or None."""
    from PIL import Image

    with Image.open(src) as im:
        sm = im.convert("RGB").resize((160, 214))
    w, h = sm.size
    px = sm.load()

    def near(c: tuple[int, ...]) -> bool:
        return sum(abs(c[i] - PANEL_RGB[i]) for i in range(3)) < 34

    ok = [[near(px[x, y]) for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    best: tuple[int, int, int, int, int] | None = None
    for y in range(h):
        for x in range(w):
            if not ok[y][x] or seen[y][x]:
                continue
            stack, n = [(x, y)], 0
            x0, y0, x1, y1 = x, y, x, y
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                n += 1
                x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and ok[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if best is None or n > best[4]:
                best = (x0, y0, x1 + 1, y1 + 1, n)
    if best is None or best[4] < w * h * 0.12:
        return None
    x0, y0, x1, y1, _ = best
    m = 0.012  # stay off the panel border
    return (x0 / w + m, y0 / h + m, x1 / w - m, y1 / h - m)


def build_templates(
    art: dict[str, Path],
    width_in: float,
    height_in: float,
    window: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """`design:tpl_<type>` pages -> {type: {image, x_in, y_in, w_in, h_in}} (panel, inches).

    The designed page is fitted into `window` (the opening of the shared frame), so the panel
    position is given on the printed page, not on the picture."""
    wx, wy = window[0], window[1]
    ww, wh = window[2] - window[0], window[3] - window[1]
    from PIL import Image

    files: dict[str, bytes] = {}
    tpls: dict[str, Any] = {}
    for key, src in art.items():
        if not key.startswith("design:tpl_"):
            continue
        kind = key.split("design:tpl_", 1)[1]
        rect = find_panel(src)
        if rect is None:
            continue
        with Image.open(src) as im:
            bg = im.convert("RGB").resize(
                (round(width_in * 200), round(height_in * 200)), Image.Resampling.LANCZOS
            )
        buf = io.BytesIO()
        bg.save(buf, "JPEG", quality=88, optimize=True, dpi=(200, 200))
        name = f"theme/tpl_{kind}.jpg"
        files[name] = buf.getvalue()
        x0, y0, x1, y1 = rect
        tpls[kind] = {
            "image": name,
            "x_in": round((wx + x0 * ww) * width_in, 3),
            "y_in": round((wy + y0 * wh) * height_in, 3),
            "w_in": round((x1 - x0) * ww * width_in, 3),
            "h_in": round((y1 - y0) * wh * height_in, 3),
        }
    return files, tpls


def _frame_mask(src: Path) -> tuple[Any, Any]:
    """(frame as RGB, small "L" mask: 0 = empty parchment centre, 255 = frame)."""
    from PIL import Image, ImageFilter

    with Image.open(src) as im:
        rgb = im.convert("RGB")
    w, h = rgb.size
    sw, sh = 170, round(170 * h / w)
    sm = rgb.resize((sw, sh))
    px = sm.load()
    seed = px[sw // 2, sh // 2]

    def near(c: tuple[int, ...]) -> bool:
        return sum(abs(c[i] - seed[i]) for i in range(3)) < 46

    inside = [[False] * sw for _ in range(sh)]
    stack = [(sw // 2, sh // 2)]
    inside[sh // 2][sw // 2] = True
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < sw and 0 <= ny < sh and not inside[ny][nx] and near(px[nx, ny]):
                inside[ny][nx] = True
                stack.append((nx, ny))
    mask = Image.new("L", (sw, sh), 255)
    mpx = mask.load()
    for y in range(sh):
        for x in range(sw):
            if inside[y][x]:
                mpx[x, y] = 0
    # swallow stray parchment specks along the inner edge
    return rgb, mask.filter(ImageFilter.MinFilter(3))


def frame_overlay(src: Path) -> bytes:
    """The page frame with its empty parchment centre made transparent, laid over every designed
    page so the whole book shares ONE frame (owner 2026-11-21)."""
    from PIL import Image

    rgb, mask = _frame_mask(src)
    out = rgb.convert("RGBA")
    out.putalpha(mask.resize(rgb.size, Image.Resampling.BILINEAR))
    out = out.resize((1275, 1650))
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def frame_window(src: Path) -> tuple[float, float, float, float]:
    """Opening of the frame between its bars (corner ornaments ignored) -> (x0, y0, x1, y1) as
    page fractions. Designed pages are fitted into it, so the frame never hides their text."""
    _, mask = _frame_mask(src)
    sw, sh = mask.size
    px = mask.load()
    rows = range(round(sh * 0.3), round(sh * 0.7))
    cols = range(round(sw * 0.3), round(sw * 0.7))
    lefts = [next((x for x in range(sw) if px[x, y] == 0), 0) for y in rows]
    rights = [next((x for x in range(sw - 1, -1, -1) if px[x, y] == 0), sw - 1) for y in rows]
    tops = [next((y for y in range(sh) if px[x, y] == 0), 0) for x in cols]
    bots = [next((y for y in range(sh - 1, -1, -1) if px[x, y] == 0), sh - 1) for x in cols]
    pad = 0.008  # tuck the page edge slightly under the frame bars
    return (
        max(0.0, min(lefts) / sw - pad),
        max(0.0, min(tops) / sh - pad),
        min(1.0, (max(rights) + 1) / sw + pad),
        min(1.0, (max(bots) + 1) / sh + pad),
    )
