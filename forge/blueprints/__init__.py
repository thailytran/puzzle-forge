"""Blueprint library: page types with z-ordered zones per book line (docs/MYSTERY_DESIGN.md §14)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from forge.config import REPO_ROOT
from forge.layout.trim import TRIMS

BLUEPRINT_DIR = REPO_ROOT / "blueprints"
MM_PER_IN = 25.4
ZoneKind = Literal["art", "puzzle", "text", "input", "header", "footer", "watermark"]
FUNCTIONAL = ("puzzle", "text", "input")
PAGE_TYPES = (
    "inner_cover",
    "how_to_play",
    "story",
    "dossier",
    "reference",
    "main_puzzle",
    "supporting_clues",
    "interlude",
    "code_register",
    "evidence_worksheet",
    "final_meta",
    "cbn_reveal",
    "hints",
    "solutions",
    "certificate",
    "cutout",
    "notes",
)


class Zone(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    kind: ZoneKind
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    z: int = 0

    def scaled(self, sx: float, sy: float) -> Zone:
        return self.model_copy(
            update={"x": self.x * sx, "y": self.y * sy, "w": self.w * sx, "h": self.h * sy}
        )

    def overlaps(self, o: Zone) -> bool:
        return not (
            self.x + self.w <= o.x
            or o.x + o.w <= self.x
            or self.y + self.h <= o.y
            or o.y + o.h <= self.y
        )


class PageType(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variants: dict[str, list[Zone]]
    bare: bool = False
    single_sided: bool = False


class Blueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line: str
    audience: str
    base_trim: str
    binding_mm: float = 19.0
    common: list[Zone] = Field(default_factory=list)
    page_types: dict[str, PageType]

    def zones(
        self, page_type: str, variant: str = "default", trim: str | None = None
    ) -> list[Zone]:
        """Zones (common + variant), scaled to `trim`, sorted by z (bottom first)."""
        pt = self.page_types[page_type]
        zs = ([] if pt.bare else list(self.common)) + list(pt.variants[variant])
        if trim and trim != self.base_trim:
            b, t = TRIMS[self.base_trim], TRIMS[trim]
            zs = [z.scaled(t.width_in / b.width_in, t.height_in / b.height_in) for z in zs]
        return sorted(zs, key=lambda z: z.z)

    def knockout(self, page_type: str, variant: str = "default") -> list[Zone]:
        return [z for z in self.zones(page_type, variant) if z.kind in FUNCTIONAL]


def load_blueprint(line: str) -> Blueprint:
    path = BLUEPRINT_DIR / line / "line.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"no blueprint {line!r} (expected {path})")
    return Blueprint.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def validate_blueprint(bp: Blueprint) -> list[str]:
    """Problems (empty = OK)."""
    out: list[str] = []
    t = TRIMS[bp.base_trim]
    w_mm, h_mm = t.width_in * MM_PER_IN, t.height_in * MM_PER_IN
    missing = [p for p in PAGE_TYPES if p not in bp.page_types]
    if missing:
        out.append(f"missing page types: {missing}")
    for name, pt in bp.page_types.items():
        if not pt.variants:
            out.append(f"{name}: no layout variant")
        for var in pt.variants:
            zs = bp.zones(name, var)
            for z in zs:
                if z.x < -0.01 or z.y < -0.01 or z.x + z.w > w_mm + 0.01 or z.y + z.h > h_mm + 0.01:
                    out.append(f"{name}/{var}/{z.name}: outside the page")
                if z.kind in FUNCTIONAL and z.x < bp.binding_mm - 0.01:
                    out.append(f"{name}/{var}/{z.name}: inside the binding margin")
                if z.kind == "header" and z.y + z.h > 13:
                    out.append(f"{name}/{var}/{z.name}: header must sit in the top margin")
                if z.kind == "footer" and z.y < 260:
                    out.append(f"{name}/{var}/{z.name}: footer must sit in the bottom margin")
            func = [z for z in zs if z.kind in FUNCTIONAL]
            for i, a in enumerate(func):
                for b in func[i + 1 :]:
                    if a.overlaps(b):
                        out.append(f"{name}/{var}: functional zones {a.name} and {b.name} overlap")
    return out


def blueprint_lines() -> list[str]:
    return sorted(p.parent.name for p in Path(BLUEPRINT_DIR).glob("*/line.yaml"))
