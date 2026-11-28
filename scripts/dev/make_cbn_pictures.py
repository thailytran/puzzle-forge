"""Draws the colour-by-number evidence pictures (pixel art) into forge/puzzles/cbn/pictures.py.

Run by hand when a picture is added or changed: `python scripts/dev/make_cbn_pictures.py`.
The book build never runs this: it reads the generated, version-controlled rows.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

W, H = 32, 30
NAVY, RED, GOLD, GREEN, SKY, WHITE, BROWN = 1, 2, 3, 4, 5, 6, 7
PALETTE = [
    ("Navy", "#1f2f5a"),
    ("Red", "#d62828"),
    ("Gold", "#f6b21b"),
    ("Green", "#2a9d57"),
    ("Sky", "#8fd0f0"),
    ("White", "#ffffff"),
    ("Brown", "#6b3e1e"),
]


def canvas(
    bg: int, ground: int | None = WHITE, at: int = 28
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    g = Image.new("P", (W, H), bg)
    d = ImageDraw.Draw(g)
    if ground is not None:
        d.rectangle([0, at, W - 1, H - 1], fill=ground)
    return g, d


def flakes(d: ImageDraw.ImageDraw, pts: list[tuple[int, int]], c: int = WHITE) -> None:
    for p in pts:
        d.point(p, fill=c)


def lantern() -> Image.Image:
    g, d = canvas(NAVY)
    flakes(d, [(3, 3), (8, 8), (27, 4), (24, 11), (5, 16), (29, 19), (2, 22), (12, 2), (20, 5)])
    d.arc([12, 1, 19, 8], 180, 360, fill=BROWN)
    d.rectangle([14, 5, 17, 7], fill=BROWN)
    d.polygon([(9, 11), (22, 11), (19, 8), (12, 8)], fill=BROWN)
    d.rectangle([10, 12, 21, 23], fill=GOLD)
    for x in (10, 21):
        d.rectangle([x, 12, x, 23], fill=BROWN)
    d.rectangle([15, 12, 16, 13], fill=BROWN)
    d.ellipse([13, 14, 18, 22], fill=RED)
    d.ellipse([14, 17, 17, 22], fill=WHITE)
    d.rectangle([9, 24, 22, 25], fill=BROWN)
    d.rectangle([11, 26, 20, 27], fill=BROWN)
    for x in (5, 25):
        d.rectangle([x, 25, x + 1, 27], fill=GREEN)
        d.point((x + 1, 24), fill=RED)
    return g


def scarf() -> Image.Image:
    g, d = canvas(SKY)
    flakes(d, [(3, 5), (27, 3), (4, 20), (28, 17), (2, 12), (29, 22), (24, 8)])
    d.ellipse([6, 3, 25, 15], fill=RED)
    d.ellipse([10, 6, 21, 11], fill=SKY)
    d.rectangle([11, 13, 18, 25], fill=RED)
    d.polygon([(18, 13), (26, 16), (24, 25), (18, 23)], fill=RED)
    for y in (16, 19, 22):
        d.rectangle([11, y, 18, y], fill=WHITE)
    for y in (18, 21):
        d.line([(19, y - 1), (25, y + 1)], fill=WHITE)
    for x in (11, 13, 15, 17):
        d.rectangle([x, 26, x, 28], fill=GOLD)
    for x in (20, 22, 24):
        d.rectangle([x, 26, x, 27], fill=GOLD)
    d.rectangle([8, 7, 9, 10], fill=GREEN)
    d.rectangle([22, 7, 23, 10], fill=GREEN)
    return g


def boot() -> Image.Image:
    g, d = canvas(SKY)
    flakes(d, [(3, 4), (28, 6), (25, 12), (4, 15), (29, 18), (2, 22)])
    d.rectangle([9, 2, 18, 20], fill=BROWN)  # shaft
    d.rectangle([9, 2, 18, 4], fill=RED)  # cuff
    d.polygon([(9, 18), (26, 18), (28, 22), (28, 25), (9, 25)], fill=BROWN)  # foot
    d.rectangle([8, 26, 28, 27], fill=NAVY)  # sole
    d.rectangle([8, 24, 12, 27], fill=NAVY)  # heel
    for y in (7, 10, 13, 16):
        d.rectangle([14, y, 17, y], fill=GOLD)  # laces
    d.rectangle([19, 19, 24, 19], fill=GOLD)
    for x in (3, 5):  # prints in the snow
        d.rectangle([x, 28, x, 29], fill=SKY)
    return g


def bridge() -> Image.Image:
    g, d = canvas(SKY, NAVY, 21)  # river
    d.ellipse([22, 1, 28, 7], fill=GOLD)  # sun
    d.rectangle([0, 12, W - 1, 15], fill=BROWN)  # deck
    d.rectangle([0, 9, W - 1, 9], fill=BROWN)  # rail
    for x in range(1, W, 5):
        d.rectangle([x, 9, x, 12], fill=BROWN)
    d.rectangle([0, 16, W - 1, 23], fill=BROWN)  # stone body
    for x0 in (3, 18):  # two arches
        d.ellipse([x0, 16, x0 + 10, 28], fill=SKY)
        d.rectangle([x0, 22, x0 + 10, 29], fill=NAVY)
    for y in (25, 28):
        for x in (2, 12, 22):
            d.rectangle([x, y, x + 4, y], fill=WHITE)  # ripples
    d.rectangle([0, 18, 1, 21], fill=GREEN)
    d.rectangle([30, 18, 31, 21], fill=GREEN)
    return g


def ladder() -> Image.Image:
    g, d = canvas(SKY)
    d.rectangle([0, 0, 13, 26], fill=RED)  # wall
    for y in range(2, 26, 4):
        d.rectangle([0, y, 13, y], fill=WHITE)
    d.rectangle([3, 8, 9, 15], fill=GOLD)  # lit window
    d.rectangle([6, 8, 6, 15], fill=BROWN)
    d.rectangle([3, 11, 9, 11], fill=BROWN)
    for x in (16, 25):  # rails, leaning a little
        d.line([(x, 26), (x - 2, 1)], fill=BROWN, width=2)
    for y in (4, 8, 12, 16, 20, 24):
        d.rectangle([15, y, 25, y], fill=BROWN)
    d.rectangle([27, 20, 30, 26], fill=GREEN)  # bush
    d.point((28, 21), fill=RED)
    d.point((29, 23), fill=RED)
    flakes(d, [(20, 2), (29, 6), (28, 14)])
    return g


def note() -> Image.Image:
    g, d = canvas(BROWN, None)  # a desk
    d.polygon([(6, 2), (25, 2), (25, 24), (21, 27), (6, 27)], fill=WHITE)  # paper, folded corner
    d.polygon([(21, 27), (21, 24), (25, 24)], fill=SKY)
    for y, x1 in ((5, 22), (8, 19), (11, 22), (14, 17), (17, 21), (20, 14)):
        d.rectangle([9, y, x1, y], fill=NAVY)  # writing
    d.ellipse([16, 19, 21, 24], fill=RED)  # wax seal
    d.point((18, 21), fill=GOLD)
    d.point((19, 22), fill=GOLD)
    d.line([(27, 27), (30, 8)], fill=GOLD, width=2)  # pencil
    d.rectangle([29, 5, 30, 7], fill=RED)
    d.rectangle([1, 5, 3, 12], fill=GREEN)  # holly on the desk
    d.point((2, 13), fill=RED)
    return g


def glove() -> Image.Image:
    g, d = canvas(NAVY)
    flakes(d, [(3, 3), (27, 5), (29, 15), (2, 17), (5, 23), (26, 22), (14, 1)])
    d.rounded_rectangle([9, 4, 21, 20], radius=5, fill=GREEN)  # mitten
    d.ellipse([19, 10, 26, 17], fill=GREEN)  # thumb
    d.rectangle([10, 20, 20, 26], fill=RED)  # cuff
    for x in (12, 15, 18):
        d.rectangle([x, 20, x, 26], fill=WHITE)
    for p in ((15, 7), (13, 9), (17, 9), (15, 11), (15, 9), (12, 12), (18, 12)):
        d.point(p, fill=WHITE)  # snowflake pattern
    d.rectangle([14, 14, 16, 14], fill=GOLD)
    return g


def paw() -> Image.Image:
    g, d = canvas(SKY, WHITE, 0)  # snow everywhere, sky-blue prints
    d.rectangle([0, 0, W - 1, 3], fill=NAVY)
    flakes(d, [(4, 1), (12, 2), (21, 1), (28, 2)])
    d.ellipse([10, 15, 21, 26], fill=BROWN)  # pad
    for x0, y0 in ((6, 10), (12, 6), (18, 6), (23, 10)):
        d.ellipse([x0, y0, x0 + 4, y0 + 5], fill=BROWN)  # toes
    for x0, y0 in ((2, 24), (26, 25)):  # small trail
        d.ellipse([x0, y0, x0 + 3, y0 + 3], fill=SKY)
    d.rectangle([27, 6, 30, 9], fill=GREEN)
    d.point((28, 5), fill=RED)
    d.rectangle([2, 15, 6, 16], fill=GOLD)  # dropped ribbon
    return g


PICS = {
    "lantern": lantern,
    "scarf": scarf,
    "boot": boot,
    "bridge": bridge,
    "ladder": ladder,
    "note": note,
    "glove": glove,
    "paw": paw,
}


def rows_of(g: Image.Image) -> list[str]:
    return ["".join(str(g.getpixel((x, y))) for x in range(W)) for y in range(H)]


def main() -> None:
    out = [
        '"""Colour-by-number evidence pictures (pixel art drawn for this project).',
        "",
        "Generated by scripts/dev/make_cbn_pictures.py - edit the script, not this file.",
        'A code "#lantern" stands for PICTURES["lantern"]; every digit is a palette number."""',
        "",
        "from __future__ import annotations",
        "",
        f"PICTURE_W, PICTURE_H = {W}, {H}",
        "PICTURE_PALETTE: list[tuple[str, str]] = [",
        *[f'    ("{n}", "{h}"),' for n, h in PALETTE],
        "]",
        "PICTURES: dict[str, tuple[str, ...]] = {",
    ]
    for name, fn in PICS.items():
        out.append(f'    "{name}": (')
        out += [f'        "{r}",' for r in rows_of(fn())]
        out.append("    ),")
    out.append("}")
    Path(__file__).resolve().parents[2].joinpath("forge/puzzles/cbn/pictures.py").write_text(
        "\n".join(out) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
