"""Hidden-object catalog for the Adventure line (ROADMAP P9.1).

Every object a search page may hide is listed here once, with the rooms (tags) it suits. The catalog
is what lets code pick a chapter's object list and give each object an icon brief: Gemini draws one
icon sheet per chapter in list order (`icon_sheet_brief`), code cuts it into icons
(`forge.adventure.pages.split_icon_sheet`).

Rules for an object (owner 2026-11-20, docs/adventures/snow_queens_library_script.md):
  * concrete, drawable as a clear outline at icon size, recognisable without colour;
  * one or two words, no brand names;
  * never the answer word of a puzzle in the same chapter (checked in `forge.adventure.frame`).
"""

from __future__ import annotations

import random
import re

# name -> room tags. Tags: library, maps, clocks, garden, sky, sewing, mirrors, winter, treasure,
# kitchen, music, travel, toys, nature (free combination; a room asks for one or more tags).
CATALOG: dict[str, tuple[str, ...]] = {
    # library / study
    "teacup": ("library", "kitchen", "mirrors"),
    "bookmark": ("library",),
    "pocket watch": ("library", "clocks"),
    "mitten": ("winter", "library"),
    "quill": ("library", "maps"),
    "feather quill": ("library", "treasure"),
    "candle": ("library", "mirrors", "treasure"),
    "spectacles": ("library", "sewing"),
    "inkwell": ("library", "maps"),
    "snow globe": ("winter", "library", "toys"),
    "rolled scroll": ("library", "maps", "treasure"),
    "brass bell": ("library", "clocks", "music"),
    "pine cone": ("winter", "nature", "garden"),
    "open book": ("library", "treasure"),
    "magnifying glass": ("library", "maps", "sky"),
    "reading lamp": ("library",),
    "oil lamp": ("library", "treasure", "travel"),
    "paper airplane": ("library", "toys"),
    "stack of letters": ("library", "travel"),
    "wax candle stub": ("library",),
    "pencil": ("library", "maps", "sewing"),
    "envelope": ("library", "travel"),
    "teapot": ("kitchen", "library"),
    "cookie": ("kitchen", "winter"),
    "mug": ("kitchen", "winter"),
    # maps / travel
    "compass": ("maps", "travel", "sky"),
    "spyglass": ("maps", "travel", "sky"),
    "sextant": ("maps", "sky"),
    "tiny sailboat": ("maps", "travel", "toys"),
    "anchor": ("maps", "travel"),
    "lighthouse": ("maps", "travel"),
    "wax seal": ("maps", "library", "treasure"),
    "pushpin": ("maps",),
    "folded postcard": ("maps", "travel"),
    "hot-air balloon": ("maps", "travel", "sky"),
    "ink pen": ("maps", "library"),
    "brass ruler": ("maps", "sewing"),
    "globe": ("maps", "library"),
    "suitcase": ("travel",),
    "ship in a bottle": ("maps", "travel", "toys"),
    "train ticket": ("travel",),
    "seashell": ("maps", "travel", "nature"),
    # clocks
    "hourglass": ("clocks", "treasure"),
    "cuckoo": ("clocks", "nature"),
    "gear": ("clocks",),
    "wind-up key": ("clocks", "toys"),
    "sundial": ("clocks", "garden"),
    "music box": ("clocks", "music", "toys"),
    "pendulum": ("clocks",),
    "bell jar": ("clocks", "garden"),
    "calendar": ("clocks", "library"),
    "pocket watch chain": ("clocks",),
    "tiny anvil": ("clocks",),
    "feather duster": ("clocks", "library"),
    "alarm clock": ("clocks",),
    "screwdriver": ("clocks",),
    "oil can": ("clocks",),
    "metronome": ("clocks", "music"),
    # garden / greenhouse
    "watering can": ("garden",),
    "trowel": ("garden",),
    "seed packet": ("garden",),
    "snail": ("garden", "nature"),
    "ladybird": ("garden", "nature"),
    "bee skep": ("garden",),
    "garden shears": ("garden",),
    "clay pot": ("garden",),
    "rose": ("garden", "mirrors"),
    "tiny ladder": ("garden", "toys"),
    "wheelbarrow": ("garden",),
    "bird bath": ("garden",),
    "butterfly": ("garden", "nature"),
    "mushroom": ("garden", "nature", "winter"),
    "acorn": ("nature", "garden", "winter"),
    "garden gloves": ("garden",),
    "rake": ("garden",),
    "birdhouse": ("garden", "nature", "winter"),
    "tulip": ("garden",),
    # sky / observatory
    "telescope": ("sky",),
    "crescent moon": ("sky", "winter"),
    "comet": ("sky",),
    "planet model": ("sky",),
    "star chart": ("sky", "maps"),
    "brass lens": ("sky",),
    "shooting star": ("sky",),
    "ladder": ("sky", "library", "garden"),
    "notebook": ("sky", "library"),
    "lantern": ("sky", "winter", "travel"),
    "tiny rocket": ("sky", "toys"),
    "cloud": ("sky",),
    "kite": ("sky", "toys"),
    "weather vane": ("sky", "garden"),
    "owl feather": ("sky", "nature", "winter"),
    # sewing / tapestry
    "thimble": ("sewing",),
    "needle": ("sewing",),
    "scissors": ("sewing", "library"),
    "button": ("sewing",),
    "spool": ("sewing",),
    "pin cushion": ("sewing",),
    "tape measure": ("sewing",),
    "tiny dress form": ("sewing",),
    "ribbon": ("sewing", "treasure", "mirrors"),
    "bobbin": ("sewing",),
    "sewing basket": ("sewing",),
    "patchwork square": ("sewing",),
    "ball of yarn": ("sewing", "winter"),
    "knitting needles": ("sewing", "winter"),
    "safety pin": ("sewing",),
    "iron": ("sewing",),
    # mirrors / dressing room
    "hand mirror": ("mirrors",),
    "picture frame": ("mirrors", "library"),
    "candlestick": ("mirrors", "treasure", "library"),
    "feather boa": ("mirrors",),
    "fan": ("mirrors", "music"),
    "lace glove": ("mirrors", "treasure"),
    "perfume bottle": ("mirrors",),
    "hairbrush": ("mirrors",),
    "tiny crown": ("mirrors", "treasure", "toys"),
    "cameo brooch": ("mirrors", "treasure"),
    "powder puff": ("mirrors",),
    "silver tray": ("mirrors", "kitchen"),
    "comb": ("mirrors",),
    "pearl necklace": ("mirrors", "treasure"),
    "top hat": ("mirrors", "music"),
    # treasure / gate / winter
    "silver key": ("treasure",),
    "crown": ("treasure",),
    "snowflake": ("winter", "treasure"),
    "pedestal": ("treasure",),
    "glass shard": ("treasure", "mirrors"),
    "silver bell": ("treasure", "winter", "music"),
    "star": ("treasure", "sky", "winter"),
    "treasure chest": ("treasure",),
    "padlock": ("treasure",),
    "goblet": ("treasure",),
    "scarf": ("winter",),
    "ice skate": ("winter", "toys"),
    "sled": ("winter", "toys"),
    "holly sprig": ("winter", "garden"),
    "icicle": ("winter",),
    "snowman figurine": ("winter", "toys"),
    "wooden horse": ("toys",),
    "spinning top": ("toys",),
    "toy soldier": ("toys", "music"),
    "violin": ("music",),
    "drum": ("music", "toys"),
    "harp": ("music",),
    "trumpet": ("music",),
    "music sheet": ("music", "library"),
}

MIN_OBJECTS, MAX_OBJECTS = 12, 20  # owner 2026-11-20: 12-20 objects per search page
_NAME = re.compile(r"^[a-z][a-z' -]{1,24}[a-z]$")


def norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def letters(name: str) -> str:
    """Object name as it would appear in a word grid (WATERINGCAN)."""
    return re.sub(r"[^A-Z]", "", name.upper())


def in_catalog(name: str) -> bool:
    return norm(name) in CATALOG


def object_problems(names: list[str], answers: list[str]) -> list[str]:
    """Problems of one search page's object list (empty = OK)."""
    p: list[str] = []
    seen: set[str] = set()
    if not MIN_OBJECTS <= len(names) <= MAX_OBJECTS:
        p.append(f"{len(names)} objects; a search page lists {MIN_OBJECTS}-{MAX_OBJECTS}")
    for raw in names:
        n = norm(raw)
        if n in seen:
            p.append(f"object {n!r} is listed twice")
        seen.add(n)
        if not _NAME.match(n) or len(n.split()) > 3:
            p.append(f"object {n!r} must be 1-3 plain words")
        if n not in CATALOG:
            p.append(f"object {n!r} is not in the catalog (no icon brief): add it or pick another")
        for a in answers:
            if a and a.upper() in letters(n):
                p.append(f"object {n!r} contains the puzzle answer {a!r}")
    return p


def pick_objects(
    tags: list[str],
    n: int,
    seed: int,
    exclude: set[str] | None = None,
    answers: tuple[str, ...] = (),
) -> list[str]:
    """Deterministic pick of `n` catalog objects for a room (objects matching more tags first)."""
    if not MIN_OBJECTS <= n <= MAX_OBJECTS:
        raise ValueError(f"n must be {MIN_OBJECTS}-{MAX_OBJECTS}")
    skip = {norm(x) for x in (exclude or set())}
    want = set(tags)
    pool = [
        name
        for name, t in CATALOG.items()
        if name not in skip
        and want & set(t)
        and not any(a and a.upper() in letters(name) for a in answers)
    ]
    rng = random.Random(seed)
    rng.shuffle(pool)
    pool.sort(key=lambda name: -len(want & set(CATALOG[name])))  # stable: shuffled ties stay mixed
    if len(pool) < n:
        raise ValueError(f"only {len(pool)} catalog objects fit tags {sorted(want)}")
    return pool[:n]


def icon_sheet_brief(names: list[str], cols: int = 4) -> str:
    """Gemini brief for one chapter's icon sheet: a fixed grid, one object per cell, list order."""
    rows = -(-len(names) // cols)
    order = "; ".join(f"{i}. {norm(x)}" for i, x in enumerate(names, 1))
    return (
        f"Icon sheet, {cols} columns x {rows} rows on plain white, one small black line-art icon "
        f"centred in each cell, in this reading order (left to right, top to bottom): {order}. "
        "Clean even outlines, no shading, no text, no numbers, no frames, equal size, generous "
        "white space between cells."
    )
