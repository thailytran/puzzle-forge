"""Brand config + pre-tinted watermark art (no PDF transparency: colours are mixed with white)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from forge.config import REPO_ROOT

BRAND_PATH = REPO_ROOT / "configs" / "brand.yaml"


@dataclass(frozen=True)
class Brand:
    name: str
    website: str
    logo: Path
    emblem: Path
    color: str
    year: int
    license_line: str
    classroom_copy_allowed: bool
    wm_opacity_color: float
    wm_opacity_gray: float
    wm_size_in: float
    microtext_pt: float
    placeholder: bool

    @property
    def microtext(self) -> str:
        return f"© {self.year} {self.name} • {self.website}"


@lru_cache(maxsize=4)
def load_brand(path: Path = BRAND_PATH) -> Brand:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    wm = raw.get("watermark", {})
    return Brand(
        name=str(raw["brand_name"]),
        website=str(raw["website"]),
        logo=REPO_ROOT / raw["logo"],
        emblem=REPO_ROOT / raw["emblem"],
        color=str(raw["primary_color"]),
        year=int(raw["copyright_year"]),
        license_line=str(raw["license_line"]),
        classroom_copy_allowed=bool(raw.get("classroom_copy_allowed", False)),
        wm_opacity_color=float(wm.get("opacity_color", 0.05)),
        wm_opacity_gray=float(wm.get("opacity_gray", 0.035)),
        wm_size_in=float(wm.get("size_in", 2.6)),
        microtext_pt=float(raw.get("microtext_pt", 6.8)),
        placeholder=bool(raw.get("placeholder", False)),
    )


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_gray(hex_color: str) -> str:
    r, g, b = _rgb(hex_color)
    y = round(0.299 * r + 0.587 * g + 0.114 * b)
    return f"#{y:02x}{y:02x}{y:02x}"


def tint(hex_color: str, strength: float) -> str:
    """Colour of `hex_color` printed at `strength` on white paper (e.g. 0.05 = 5 %)."""
    r, g, b = _rgb(hex_color)
    mix = [round(255 - (255 - c) * strength) for c in (r, g, b)]
    return "#" + "".join(f"{c:02x}" for c in mix)


def recolor_svg(svg: str, color: str) -> str:
    """Replace every non-white hex colour of a single-colour SVG with `color`."""
    return re.sub(r"#(?!ffffff\b|fff\b)[0-9a-fA-F]{6}\b|#(?!fff\b)[0-9a-fA-F]{3}\b", color, svg)


def art_files(brand: Brand, color: bool) -> dict[str, bytes]:
    """Watermark emblem (tinted) + corner logo for a colour or grayscale edition."""
    base = brand.color if color else to_gray(brand.color)
    strength = brand.wm_opacity_color if color else brand.wm_opacity_gray
    emblem = recolor_svg(brand.emblem.read_text(encoding="utf-8"), tint(base, strength))
    logo = recolor_svg(brand.logo.read_text(encoding="utf-8"), base)
    return {"brand/emblem.svg": emblem.encode(), "brand/logo.svg": logo.encode()}
