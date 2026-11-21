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


def place_art(
    pages: list[Any],
    requests: list[dict[str, Any]],
    art: dict[str, Path],
    text_width_in: float,
    text_height_in: float,
    make_page: Callable[..., Any],
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
        if req.get("zone") == "portraits":
            inserts.append((n, make_page(kind="text", title=PORTRAITS_TITLE, blocks=[block])))
        else:
            pages[n - 1].blocks.insert(0, block)
            if req.get("zone") == "scene":
                pages[n - 1].blocks.insert(1, {"kind": "spacer", "height_in": 0.15})
        placed.append(key)
    for n, page in sorted(inserts, key=lambda x: -x[0]):
        pages.insert(n, page)
    return files, {"placed": placed, "missing": missing, "pages_added": len(inserts)}


# ---------------------------------------------------------------- page theme (Studio design kit)
FRAME_SHARE = (
    0.1,
    0.095,
)  # frame border width / height as a share of the page (the centre is empty parchment)


def theme_margins(width_in: float, height_in: float) -> dict[str, float]:
    """Margins that keep text inside the empty centre of the page frame."""
    sx, sy = FRAME_SHARE
    side = round(max(0.75, width_in * sx), 2)
    return {
        "inside": side,
        "outside": side,
        "top": round(max(0.8, height_in * sy), 2),
        "bottom": round(max(1.15, height_in * 0.13), 2),  # corner ornaments (lantern, pine) sit low
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
