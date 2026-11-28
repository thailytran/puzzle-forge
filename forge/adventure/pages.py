"""Designed pages of an Adventure book, composed as 300 dpi pictures (ROADMAP P9.2, P9.3).

Owner look (2026-11-21): black-and-white line art to colour, an ornate frame on every page.
  * search page (right page of the chapter spread): the full-page line-art scene inside the frame,
    a narrow side column "Puzzle N" with the hidden objects (icon + name + a "found" box);
  * story page (left page): "Chapter N | Title" ribbon at the top, the story set by Typst in the
    calm upper box (`STORY_BOX`), the line-art vignette in the lower part of the same frame;
  * answer key: the scene with a numbered circle on every object, from the Gemini self-check
    positions that the owner ticked in the review UI (code cannot verify art);
  * the lock diagram (Lock Log, key pages, final challenge).

Art comes from HALOSPARK Studio (keys in docs/adventures/STUDIO_ADVENTURE.md). Missing art leaves
a labelled placeholder, so a book can be laid out and reviewed before every picture exists.
Pure Pillow; every function returns PNG bytes.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

DPI = 300
FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"
INK = (28, 26, 24)
SOFT = (120, 116, 110)
FOOT_IN = 0.45  # bottom band kept free for the page number (Typst footer)
FRAME_IN = 0.42  # outer frame inset from the trim edge
# story text box (page fractions x, y, w, h): under the ribbon, above the vignette
STORY_BOX = (0.135, 0.150, 0.730, 0.400)
VIGNETTE_BOX = (0.115, 0.575, 0.770, 0.325)


def font(size_px: int, kind: str = "serif") -> Any:
    name = {
        "serif": "YoungSerif-Regular.ttf",
        "sans": "AtkinsonHyperlegible-Regular.ttf",
        "bold": "AtkinsonHyperlegible-Bold.ttf",
    }[kind]
    try:
        return ImageFont.truetype(str(FONTS / name), size_px)
    except OSError:  # fonts missing: Pillow's own font keeps tests and previews working
        return ImageFont.load_default(size_px)


def _px(inches: float) -> int:
    return round(inches * DPI)


def blank(width_in: float, height_in: float) -> Image.Image:
    return Image.new("RGB", (_px(width_in), _px(height_in)), "white")


def png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True, dpi=(DPI, DPI))
    return buf.getvalue()


def line_art(src: Path | None, box: tuple[int, int], label: str = "") -> Image.Image:
    """Studio picture fitted (not cropped) into `box`, kept black and white for colouring;
    no picture -> a dashed placeholder naming the missing art key."""
    w, h = box
    if src is not None and Path(src).is_file():
        with Image.open(src) as im:
            g = ImageOps.grayscale(im.convert("RGB"))
        g = ImageOps.autocontrast(g, cutoff=1)
        g = g.point(lambda v: 255 if v > 200 else (0 if v < 90 else v))  # crisp lines, white paper
        g = ImageOps.contain(g, (w, h), Image.Resampling.LANCZOS)
        out = Image.new("RGB", (w, h), "white")
        out.paste(g.convert("RGB"), ((w - g.width) // 2, (h - g.height) // 2))
        return out
    out = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(out)
    dash = max(12, w // 60)
    for x in range(0, w, dash * 2):
        d.line([(x, 2), (min(w, x + dash), 2)], fill=SOFT, width=4)
        d.line([(x, h - 3), (min(w, x + dash), h - 3)], fill=SOFT, width=4)
    for y in range(0, h, dash * 2):
        d.line([(2, y), (2, min(h, y + dash))], fill=SOFT, width=4)
        d.line([(w - 3, y), (w - 3, min(h, y + dash))], fill=SOFT, width=4)
    f = font(max(24, w // 28), "sans")
    d.multiline_text(
        (w // 2, h // 2),
        f"art: {label}\n(waiting for Studio)",
        fill=SOFT,
        font=f,
        anchor="mm",
        align="center",
    )
    return out


# --------------------------------------------------------------------------- frame


def _snowflake(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, width: int) -> None:
    import math

    for k in range(6):
        a = math.pi / 3 * k
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        d.line([(cx, cy), (x, y)], fill=INK, width=width)
        for t in (0.55, 0.8):  # two pairs of side branches per arm
            bx, by = cx + r * t * math.cos(a), cy + r * t * math.sin(a)
            for s in (-1, 1):
                b = a + s * math.pi / 4
                ln = r * (0.32 if t < 0.7 else 0.2)
                d.line(
                    [(bx, by), (bx + ln * math.cos(b), by + ln * math.sin(b))],
                    fill=INK,
                    width=width,
                )
    d.ellipse([cx - r // 7, cy - r // 7, cx + r // 7, cy + r // 7], outline=INK, width=width)


def draw_frame(im: Image.Image, border: Path | None = None) -> tuple[int, int, int, int]:
    """Ornate frame on the page (Studio `design:border` picture, else a code-drawn frost frame).
    Returns the clear inner area (x0, y0, x1, y1) in pixels."""
    w, h = im.size
    o = _px(FRAME_IN)
    bottom = h - _px(FOOT_IN) - _px(0.3)  # corner medallions stay out of the number band
    if border is not None and Path(border).is_file():
        with Image.open(border) as b:
            fr = b.convert("RGBA").resize((w - 2 * o, bottom - o), Image.Resampling.LANCZOS)
        im.paste(fr, (o, o), fr)
        pad = _px(0.55)
        return o + pad, o + pad, w - o - pad, bottom - pad
    d = ImageDraw.Draw(im)
    d.rectangle([o, o, w - o, bottom], outline=INK, width=9)
    g = _px(0.09)
    d.rectangle([o + g, o + g, w - o - g, bottom - g], outline=INK, width=3)
    r = _px(0.2)
    for cx, cy in ((o, o), (w - o, o), (o, bottom), (w - o, bottom)):  # corner medallions
        d.ellipse(
            [cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10], fill="white", outline=INK, width=5
        )
        _snowflake(d, cx, cy, r, 4)
    step = _px(0.62)  # little ticks of frost lace along the inner rule
    for x in range(o + 2 * r, w - o - 2 * r, step):
        for y, s in ((o + g, 1), (bottom - g, -1)):
            d.polygon([(x - 14, y), (x + 14, y), (x, y + s * 22)], outline=INK, width=2)
    for y in range(o + 2 * r, bottom - 2 * r, step):
        for x, s in ((o + g, 1), (w - o - g, -1)):
            d.polygon([(x, y - 14), (x, y + 14), (x + s * 22, y)], outline=INK, width=2)
    pad = _px(0.22)
    return o + g + pad, o + g + pad, w - o - g - pad, bottom - g - pad


def ribbon(im: Image.Image, text: str, cy: int, x0: int, x1: int) -> int:
    """Heading ribbon (outline only: colourable) centred at height `cy`; returns its bottom y."""
    d = ImageDraw.Draw(im)
    size = _px(0.30)
    f = font(size)
    while d.textlength(text, font=f) > (x1 - x0) * 0.78 and size > 30:
        size -= 4
        f = font(size)
    tw = d.textlength(text, font=f)
    half = int(tw / 2 + _px(0.35))
    cx = (x0 + x1) // 2
    hh = _px(0.30)
    top, bot = cy - hh, cy + hh
    tail = _px(0.32)
    for s in (-1, 1):  # folded tails behind the band
        xa = cx + s * half
        xb = xa + s * tail
        d.polygon(
            [
                (xa, top + 22),
                (xb, top + 22),
                (xb - s * 30, cy + 11),
                (xb, bot + 22),
                (xa, bot + 22),
            ],
            fill="white",
            outline=INK,
            width=4,
        )
    d.rectangle([cx - half, top, cx + half, bot], fill="white", outline=INK, width=5)
    d.text((cx, cy), text, fill=INK, font=f, anchor="mm")
    return bot + 22


# --------------------------------------------------------------------------- pages


def story_page(
    heading: str,
    vignette: Path | None,
    width_in: float = 8.5,
    height_in: float = 11.0,
    border: Path | None = None,
    label: str = "",
) -> bytes:
    """Left page of the spread: frame + ribbon + vignette; Typst sets the story in STORY_BOX."""
    im = blank(width_in, height_in)
    x0, y0, x1, _y1 = draw_frame(im, border)
    ribbon(im, heading, y0 + _px(0.45), x0, x1)
    w, h = im.size
    vx, vy, vw, vh = VIGNETTE_BOX
    pic = line_art(vignette, (round(vw * w), round(vh * h)), label or "vignette")
    im.paste(pic, (round(vx * w), round(vy * h)))
    return png(im)


def search_page(
    no: int,
    names: list[str],
    scene: Path | None,
    icons: list[bytes | None] | None = None,
    width_in: float = 8.5,
    height_in: float = 11.0,
    border: Path | None = None,
    label: str = "",
) -> bytes:
    """Right page of the spread: the scene fills the frame, the object column sits on its right."""
    im = blank(width_in, height_in)
    x0, y0, x1, y1 = draw_frame(im, border)
    d = ImageDraw.Draw(im)
    col_w = round((x1 - x0) * 0.22)
    gap = _px(0.12)
    sx1 = x1 - col_w - gap
    im.paste(line_art(scene, (sx1 - x0, y1 - y0), label or f"search:ch{no}"), (x0, y0))
    d.line([(sx1 + gap // 2, y0), (sx1 + gap // 2, y1)], fill=INK, width=3)
    cx0 = sx1 + gap
    f_head = font(_px(0.22))
    d.text(((cx0 + x1) // 2, y0 + _px(0.2)), f"Puzzle {no}", fill=INK, font=f_head, anchor="mm")
    d.text(
        ((cx0 + x1) // 2, y0 + _px(0.45)),
        "Find & tick",
        fill=SOFT,
        font=font(_px(0.11), "sans"),
        anchor="mm",
    )
    top = y0 + _px(0.68)
    row = (y1 - top) / max(1, len(names))
    icon_px = int(min(row * 0.58, col_w * 0.7))
    size = _px(0.13) if len(names) <= 14 else _px(0.11)
    f_name = font(size, "sans")
    box = _px(0.12)
    for i, name in enumerate(names):
        ry = round(top + i * row)
        cy = round(ry + row * 0.40)
        ic = (icons or [None] * len(names))[i] if icons and i < len(icons) else None
        if ic:
            with Image.open(io.BytesIO(ic)) as icon:
                icn = ImageOps.contain(icon.convert("RGBA"), (icon_px, icon_px))
            im.paste(icn, ((cx0 + x1) // 2 - icn.width // 2, cy - icn.height // 2), icn)
        else:  # no icon yet: the object's number in a circle
            r = icon_px // 3
            mx = (cx0 + x1) // 2
            d.ellipse([mx - r, cy - r, mx + r, cy + r], outline=SOFT, width=3)
            d.text((mx, cy), str(i + 1), fill=SOFT, font=font(r, "bold"), anchor="mm")
        ty = round(ry + row * 0.86)
        bx = cx0 + _px(0.04)
        d.rectangle([bx, ty - box // 2, bx + box, ty + box // 2], outline=INK, width=3)
        text = name.title()
        fn = f_name
        while d.textlength(text, font=fn) > x1 - bx - box - _px(0.08) and fn.size > 18:
            fn = font(fn.size - 2, "sans")
        d.text((bx + box + _px(0.05), ty), text, fill=INK, font=fn, anchor="lm")
    return png(im)


def answer_key(
    no: int,
    names: list[str],
    scene: Path | None,
    marks: list[dict[str, Any]],
    box_in: tuple[float, float],
) -> bytes:
    """Scene with numbered circles; `marks` = ticked Gemini self-check positions
    ({"name", "x", "y", "r"} as fractions of the scene picture)."""
    w, h = _px(box_in[0]), _px(box_in[1])
    if scene is None or not Path(scene).is_file():
        return png(line_art(None, (w, h), f"search:ch{no}"))
    with Image.open(scene) as raw:
        sw, sh = raw.size
    pic = line_art(scene, (w, h))
    k = min(w / sw, h / sh)
    ox, oy = (w - sw * k) / 2, (h - sh * k) / 2
    d = ImageDraw.Draw(pic)
    num = {n: i + 1 for i, n in enumerate(names)}
    f = font(max(22, w // 45), "bold")
    for m in marks:
        x, y = ox + float(m["x"]) * sw * k, oy + float(m["y"]) * sh * k
        r = max(18, float(m.get("r", 0.04)) * sw * k)
        lw = max(4, w // 400)  # black ring with a white halo: reads in black-and-white print
        d.ellipse([x - r, y - r, x + r, y + r], outline="white", width=lw * 3)
        d.ellipse([x - r, y - r, x + r, y + r], outline=INK, width=lw)
        lbl = str(num.get(str(m.get("name", "")).lower(), "?"))
        d.text(
            (x + r * 0.75, y - r * 0.75),
            lbl,
            fill=INK,
            font=f,
            anchor="mm",
            stroke_width=5,
            stroke_fill="white",
        )
    return png(pic)


def lock_diagram(n: int, filled: dict[int, str] | None = None, width_in: float = 5.6) -> bytes:
    """The lock of the final door: N round slots with their numbers, empty to write in."""
    w = _px(width_in)
    r = min(_px(0.36), w // (2 * n + 2))
    h = 4 * r + _px(0.3)
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    step = (w - 2 * r) / max(1, n - 1) if n > 1 else 0
    f_num = font(max(18, r // 2), "bold")
    f_let = font(int(r * 1.1))
    d.rounded_rectangle([4, r // 2, w - 5, h - 5], radius=r, outline=INK, width=5)
    for i in range(n):
        cx = round(r + i * step) if n > 1 else w // 2
        cx = min(max(cx, r + 12), w - r - 12)
        cy = r + _px(0.2)
        d.ellipse([cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8], outline=INK, width=5)
        d.text((cx, cy + r + _px(0.08)), str(i + 1), fill=INK, font=f_num, anchor="mm")
        if filled and filled.get(i + 1):
            d.text((cx, cy), filled[i + 1], fill=INK, font=f_let, anchor="mm")
    return png(im)


def split_icon_sheet(src: Path, n: int, cols: int = 4) -> list[bytes]:
    """Icon sheet drawn in a fixed grid (objects.icon_sheet_brief) -> one transparent PNG per
    object, in list order. Each cell is trimmed to its ink; an empty cell gives b"" (no icon)."""
    rows = -(-n // cols)
    with Image.open(src) as im:
        g = ImageOps.grayscale(im.convert("RGB"))
    cw, ch = g.width / cols, g.height / rows
    out: list[bytes] = []
    for i in range(n):
        r, c = divmod(i, cols)
        m = round(min(cw, ch) * 0.04)  # skip hairlines on the cell edges
        cell = g.crop(
            (round(c * cw) + m, round(r * ch) + m, round((c + 1) * cw) - m, round((r + 1) * ch) - m)
        )
        ink = cell.point(lambda v: 255 if v < 170 else 0)
        bbox = ink.getbbox()
        if bbox is None:
            out.append(b"")
            continue
        cell = cell.crop(bbox)
        alpha = cell.point(lambda v: 0 if v > 225 else 255 - v)
        rgba = Image.merge("RGBA", (*[cell.point(lambda v: 0 if v < 225 else v)] * 3, alpha))
        rgba.thumbnail((360, 360))
        buf = io.BytesIO()
        rgba.save(buf, "PNG", optimize=True)
        out.append(buf.getvalue())
    return out
