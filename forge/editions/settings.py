"""Edition settings → layout parameters (trim, margins, bleed, watermark, footer)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from forge.editions.brand import Brand, load_brand, to_gray

EditionName = Literal["kdp", "digital", "spiral"]
BINDING_IN = {"coil": 0.75, "wire-o": 0.625}


class EditionSettings(BaseModel):
    name: EditionName = "kdp"
    trim: str | None = None  # None = spec trim
    color: bool = True
    watermark: bool = True
    binding: Literal["coil", "wire-o"] = "coil"
    duplex: bool = True
    bleed: bool = False
    crop_marks: bool = False
    stamp_zone_in: float = Field(default=0.32, description="footer band reserved for order stamps")

    @property
    def label(self) -> str:
        parts = [self.name, (self.trim or "spec").replace(".", "_")]
        if self.name == "spiral":
            parts += ["color" if self.color else "gray", "duplex" if self.duplex else "simplex"]
            if self.bleed:
                parts.append("bleed")
        return "-".join(parts)

    def margins(self, kdp: dict[str, float]) -> dict[str, float]:
        if self.name == "digital":
            return {"inside": 0.5, "outside": 0.5, "top": 0.5, "bottom": 0.75}
        if self.name == "spiral":
            return {"inside": BINDING_IN[self.binding], "outside": 0.5, "top": 0.5, "bottom": 0.75}
        return kdp

    def layout_extra(self, brand: Brand | None = None) -> dict[str, Any]:
        """The `edition` object the Typst template reads."""
        b = brand or load_brand()
        accent = b.color if self.color else to_gray(b.color)
        return {
            "name": self.name,
            "simplex": self.name == "spiral" and not self.duplex,
            "bleed_in": 0.125 if self.bleed else 0.0,
            "crop_marks": self.crop_marks and self.bleed,
            "watermark": self.watermark,
            "wm_size_in": b.wm_size_in,
            "accent": accent,
            "microtext": b.microtext if self.name != "kdp" else "",
            "microtext_pt": b.microtext_pt,
        }
