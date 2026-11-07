"""`forge blueprint preview <line>`: one page per page type and variant with coloured zones."""

from __future__ import annotations

import tempfile
from pathlib import Path

from forge.blueprints import Blueprint
from forge.layout.trim import TRIMS
from forge.layout.typst_runner import compile_pdf

COLORS = {  # zone kind -> (fill, stroke)
    "art": ("#fde2c4", "#e07b00"),
    "puzzle": ("#cfe8ff", "#1565c0"),
    "text": ("#d9f2d9", "#2e7d32"),
    "input": ("#f3d6f5", "#8e24aa"),
    "header": ("#eeeeee", "#757575"),
    "footer": ("#eeeeee", "#757575"),
    "watermark": ("#fff7c2", "#b59b00"),
}


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def preview_typst(bp: Blueprint, trim: str | None = None) -> str:
    t = TRIMS[trim or bp.base_trim]
    out = [
        f"#set page(width: {t.width_in}in, height: {t.height_in}in, margin: 0pt)",
        '#set text(font: "Atkinson Hyperlegible", size: 7pt)',
    ]
    for name, pt in bp.page_types.items():
        for var in pt.variants:
            body = [
                f"place(top + left, rect(width: {bp.binding_mm}mm, height: 100%, "
                "fill: luma(92%), stroke: none))"
            ]
            for z in bp.zones(name, var, trim):
                fill, stroke = COLORS[z.kind]
                dash = "dashed" if z.kind in ("puzzle", "text", "input") else "solid"
                body.append(
                    f"place(top + left, dx: {z.x:.2f}mm, dy: {z.y:.2f}mm, rect(width: {z.w:.2f}mm, "
                    f'height: {z.h:.2f}mm, fill: rgb("{fill}"), stroke: (paint: rgb("{stroke}"), '
                    f'thickness: 0.8pt, dash: "{dash}"), inset: 3pt, '
                    f'text(fill: rgb("{stroke}"), weight: "bold", "{_esc(z.kind)}: {_esc(z.name)} '
                    f'(z{z.z})")))'
                )
            label = f"{name} / {var}" + ("  ·  single-sided" if pt.single_sided else "")
            body.append(
                f'place(bottom + right, dx: -6mm, dy: -2mm, text(size: 9pt, weight: "bold", '
                f'"{_esc(bp.line)}: {_esc(label)}"))'
            )
            out.append("#page({\n" + "\n".join(body) + "\n})")
    legend = " · ".join(f"{k}" for k in COLORS)
    out.append(
        f'#page(align(center + horizon, text(size: 12pt, "Zone kinds: {legend}. '
        'Dashed = knock-out (functional). Grey strip = binding margin.")))'
    )
    return "\n".join(out)


def render_preview(bp: Blueprint, out_pdf: Path, trim: str | None = None) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        main = Path(tmp) / "preview.typ"
        main.write_text(preview_typst(bp, trim), encoding="utf-8")
        return compile_pdf(main, out_pdf)
