"""Cell tilings for colour-by-number mosaics: every cell is a polygon with a centre.

One core for all cell shapes (square, hexagon, triangle, ...): the generator samples the code
bitmap at each cell centre, the verifier paints the solution to a raster and reads the code back,
so nothing downstream depends on the cell shape. Coordinates are in abstract units; `min_dim` is
the diameter of the largest circle that fits in a cell (what the colourist has to fill in).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from forge.puzzles.base import GenerationError
from forge.puzzles.cbn.font import H as FONT_H
from forge.puzzles.cbn.font import W as FONT_W
from forge.puzzles.cbn.font import bitmap, match

SHAPES = ("square", "hex", "triangle", "circle")
SQRT3 = math.sqrt(3.0)
MARGIN = 1.0  # units of background kept around the code frame
RASTER_PX = 12  # raster pixels per unit used by the verifier
ON_MIN, OFF_MAX = 0.62, 0.38  # a font pixel must be clearly dark / clearly light
OUTSIDE_MAX = 0.16  # share of code-coloured ink allowed to stick out of the frame


@dataclass(frozen=True)
class Cell:
    pts: tuple[tuple[float, float], ...]  # outline that is printed and coloured in
    cx: float
    cy: float
    zone: tuple[tuple[float, float], ...] = ()  # lattice territory when the outline leaves gaps

    @property
    def area(self) -> tuple[tuple[float, float], ...]:
        """Polygon the verifier paints: the territory for gapped shapes (dots), else the outline."""
        return self.zone or self.pts


@dataclass(frozen=True)
class Tiling:
    shape: str
    rows: int
    cols: int
    width: float
    height: float
    min_dim: float  # inscribed-circle diameter of one cell, in units
    cells: tuple[Cell, ...]


def _cell(pts: list[tuple[float, float]]) -> Cell:
    n = len(pts)
    return Cell(
        tuple((round(x, 6), round(y, 6)) for x, y in pts),
        round(sum(x for x, _ in pts) / n, 6),
        round(sum(y for _, y in pts) / n, 6),
    )


def _square(rows: int, cols: int) -> Tiling:
    cells = [
        _cell([(c, r), (c + 1, r), (c + 1, r + 1), (c, r + 1)])
        for r in range(rows)
        for c in range(cols)
    ]
    return Tiling("square", rows, cols, float(cols), float(rows), 1.0, tuple(cells))


def _hex(rows: int, cols: int) -> Tiling:
    """Pointy-top honeycomb, flat-to-flat width 1; odd rows shifted half a cell."""
    rad = 1 / SQRT3
    cells = []
    for r in range(rows):
        for c in range(cols):
            cx = c + 0.5 + (0.5 if r % 2 else 0.0)
            cy = rad + r * 1.5 * rad
            cells.append(
                _cell(
                    [
                        (
                            cx + rad * math.cos(math.radians(60 * k - 90)),
                            cy + rad * math.sin(math.radians(60 * k - 90)),
                        )
                        for k in range(6)
                    ]
                )
            )
    height = 2 * rad + (rows - 1) * 1.5 * rad
    return Tiling("hex", rows, cols, cols + 0.5, height, 1.0, tuple(cells))


def _triangle(rows: int, cols: int) -> Tiling:
    """Equilateral triangles of side 1, alternating up / down along each row."""
    h = SQRT3 / 2
    cells = []
    for r in range(rows):
        y = r * h
        for c in range(cols):
            x = c * 0.5
            if (r + c) % 2 == 0:
                cells.append(_cell([(x, y + h), (x + 1, y + h), (x + 0.5, y)]))
            else:
                cells.append(_cell([(x, y), (x + 1, y), (x + 0.5, y + h)]))
    return Tiling("triangle", rows, cols, (cols + 1) * 0.5, rows * h, 1 / SQRT3, tuple(cells))


CIRCLE_R = 0.44  # dot radius on a unit lattice (white gap between dots)
CIRCLE_SIDES = 24


def _circle(rows: int, cols: int) -> Tiling:
    """Dots on a square lattice; each dot owns its lattice square (gaps stay white)."""
    cells = []
    for r in range(rows):
        for c in range(cols):
            cx, cy = c + 0.5, r + 0.5
            ring = tuple(
                (
                    round(cx + CIRCLE_R * math.cos(2 * math.pi * k / CIRCLE_SIDES), 6),
                    round(cy + CIRCLE_R * math.sin(2 * math.pi * k / CIRCLE_SIDES), 6),
                )
                for k in range(CIRCLE_SIDES)
            )
            zone = ((c, r), (c + 1, r), (c + 1, r + 1), (c, r + 1))
            cells.append(Cell(ring, cx, cy, tuple((float(x), float(y)) for x, y in zone)))
    return Tiling("circle", rows, cols, float(cols), float(rows), 2 * CIRCLE_R, tuple(cells))


def make(shape: str, rows: int, cols: int) -> Tiling:
    if shape == "square":
        return _square(rows, cols)
    if shape == "hex":
        return _hex(rows, cols)
    if shape == "triangle":
        return _triangle(rows, cols)
    if shape == "circle":
        return _circle(rows, cols)
    raise GenerationError(f"cbn: unknown cell shape {shape!r} (known: {', '.join(SHAPES)})")


def from_grid(rows: int, cols: int) -> Tiling:
    """The legacy square mosaic as a tiling (row-major cell order)."""
    return _square(rows, cols)


# Per shape: lattice step (x, y), y offset of the first row band and the smallest legible font
# pixel in lattice steps (x, y). Font pixels are whole numbers of lattice steps, so a glyph is
# built from complete cells and never from slivers.
LATTICE: dict[str, tuple[float, float, float, int, int]] = {
    "square": (1.0, 1.0, 0.0, 1, 1),
    "circle": (1.0, 1.0, 0.0, 1, 1),
    "hex": (1.0, SQRT3 / 2, 1 / SQRT3 - SQRT3 / 4, 2, 2),
    "triangle": (0.5, SQRT3 / 2, 0.0, 3, 2),
}
MAX_ASPECT = 1.35  # a font pixel may be at most this much wider than tall (or taller than wide)


def frame(n_chars: int, t: Tiling) -> tuple[float, float, float, float]:
    """(pixel width, pixel height, left, top) of the centred, lattice-aligned code frame."""
    ux, uy, y0, kx_min, ky_min = LATTICE[t.shape]
    width_px = n_chars * (FONT_W + 1) - 1
    kx = int((t.width - 2 * MARGIN) / (width_px * ux) + 1e-9)
    ky = int((t.height - y0 - 2 * MARGIN) / (FONT_H * uy) + 1e-9)
    if kx < kx_min or ky < ky_min:
        raise GenerationError(
            f"cbn: a {n_chars}-character code does not fit a {t.rows}x{t.cols} {t.shape} mosaic"
        )
    if t.shape in ("square", "circle"):
        kx = ky = min(kx, ky)
    while kx > kx_min and kx * ux > MAX_ASPECT * ky * uy:
        kx -= 1
    while ky > ky_min and ky * uy > MAX_ASPECT * kx * ux:
        ky -= 1
    sx, sy = kx * ux, ky * uy
    left = math.floor((t.width - width_px * sx) / 2 / ux) * ux
    top = y0 + math.floor((t.height - y0 - FONT_H * sy) / 2 / uy) * uy
    return sx, sy, left, top


def code_cells(code: str, t: Tiling) -> list[bool]:
    """True for every cell whose centre lies on an "on" pixel of the code bitmap."""
    sx, sy, left, top = frame(len(code), t)
    bms = [bitmap(ch) for ch in code]
    out = []
    for cell in t.cells:
        gx, gy = (cell.cx - left) / sx, (cell.cy - top) / sy
        on = False
        if 0 <= gy < FONT_H and gx >= 0:
            k, px = divmod(int(gx), FONT_W + 1)
            if k < len(code) and px < FONT_W:
                on = bool(bms[k][int(gy)][px])
        out.append(on)
    return out


def raster(t: Tiling, colors: list[int]) -> Image.Image:
    """Paint the solution: one raster value per colour index (0 = paper)."""
    img = Image.new("L", (math.ceil(t.width * RASTER_PX), math.ceil(t.height * RASTER_PX)), 0)
    draw = ImageDraw.Draw(img)
    for cell, v in zip(t.cells, colors, strict=True):
        draw.polygon([(x * RASTER_PX, y * RASTER_PX) for x, y in cell.area], fill=v)
    return img


def _dark(img: Image.Image, box: tuple[float, float, float, float]) -> tuple[int, int]:
    """(code-coloured pixels, all pixels) inside a box given in units."""
    x0, y0, x1, y1 = (round(v * RASTER_PX) for v in box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 <= x0 or y1 <= y0:
        return 0, 0
    return img.crop((x0, y0, x1, y1)).histogram()[1], (x1 - x0) * (y1 - y0)


def read_raster(t: Tiling, colors: list[int], max_len: int = 4) -> str:
    """Read the revealed code from the painted picture, whatever the cell shape.

    For each possible code length the centred frame is recomputed; the length is accepted when
    every font pixel is clearly dark or clearly light, every glyph matches exactly and (almost)
    no code-coloured ink lies outside the frame."""
    img = raster(t, colors)
    total = img.histogram()[1]
    if not total:
        return "?"
    for n in range(1, max_len + 1):
        try:
            sx, sy, left, top = frame(n, t)
        except GenerationError:
            break
        out = []
        clear = True
        for k in range(n):
            block = []
            for gy in range(FONT_H):
                line = []
                for gx in range(FONT_W):
                    x = left + (k * (FONT_W + 1) + gx) * sx
                    y = top + gy * sy
                    dark, area = _dark(img, (x, y, x + sx, y + sy))
                    share = dark / area if area else 0.0
                    if OFF_MAX < share < ON_MIN:
                        clear = False
                    line.append(1 if share >= ON_MIN else 0)
                block.append(line)
            ch, err = match(block)
            out.append(ch if err == 0 else "?")
        width_px = n * (FONT_W + 1) - 1
        inside, _ = _dark(img, (left, top, left + width_px * sx, top + FONT_H * sy))
        if clear and "?" not in out and (total - inside) / total <= OUTSIDE_MAX:
            return "".join(out)
    return "?"


def _inside(pts: tuple[tuple[float, float], ...], x: float, y: float) -> bool:
    hit = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def read_centres(t: Tiling, colors: list[int], max_len: int = 4) -> str:
    """Second, independent reading: the colour of the cell under the centre of each font pixel
    (point-in-polygon lookup, no raster)."""
    dark_total = sum(v == 1 for v in colors)
    for n in range(1, max_len + 1):
        try:
            sx, sy, left, top = frame(n, t)
        except GenerationError:
            break
        out = []
        used: set[int] = set()
        for k in range(n):
            block = []
            for gy in range(FONT_H):
                line = []
                for gx in range(FONT_W):
                    x = left + (k * (FONT_W + 1) + gx + 0.5) * sx
                    y = top + (gy + 0.5) * sy
                    idx = next(
                        (i for i, c in enumerate(t.cells) if _inside(c.area, x, y)),
                        -1,
                    )
                    on = idx >= 0 and colors[idx] == 1
                    if on:
                        used.add(idx)
                    line.append(1 if on else 0)
                block.append(line)
            ch, err = match(block)
            out.append(ch if err == 0 else "?")
        if "?" not in out and dark_total >= len(used) > 0:
            width_px = n * (FONT_W + 1) - 1
            x1, y1 = left + width_px * sx, top + FONT_H * sy
            stray = sum(
                1
                for c, v in zip(t.cells, colors, strict=True)
                if v == 1 and not (left <= c.cx <= x1 and top <= c.cy <= y1)
            )
            if stray == 0:
                return "".join(out)
    return "?"
