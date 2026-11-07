"""L2 checks for editions: watermark knock-out/contrast, spiral binding margin, bleed/crop marks."""

from __future__ import annotations

from typing import Any

from forge.qa.checks import Finding, Skip, check
from forge.qa.l2 import bleed_in, edition, pdf

NOWM_PDF = "interior_nowm.pdf"
DPI = 72
DIFF = 3  # gray levels: smaller differences are anti-aliasing noise
DARKEN_MAX = {"color": 0.05, "gray": 0.04}  # max watermark darkening of white paper
BINDING_IN = {"coil": 0.75, "wire-o": 0.625}


def _renders(ctx: Any) -> list[tuple[Any, Any]]:
    """(page with watermark, same page without) as grayscale images."""
    if "wm_pairs" in ctx.extra:
        return ctx.extra["wm_pairs"]  # type: ignore[no-any-return]
    import pypdfium2 as pdfium

    ref = ctx.out_dir / NOWM_PDF
    if not ref.is_file():
        raise FileNotFoundError(f"{NOWM_PDF} missing: rebuild the edition (forge edition build)")
    a, b = pdfium.PdfDocument(str(ctx.pdf_path)), pdfium.PdfDocument(str(ref))
    try:
        pairs = [
            (
                a[i].render(scale=DPI / 72, grayscale=True).to_pil().convert("L"),
                b[i].render(scale=DPI / 72, grayscale=True).to_pil().convert("L"),
            )
            for i in range(min(len(a), len(b)))
        ]
    finally:
        a.close()
        b.close()
    ctx.extra["wm_pairs"] = pairs
    return pairs


def _needs_watermark(ctx: Any) -> dict[str, Any]:
    e = edition(ctx)
    if not e or not e.get("watermark"):
        raise Skip("no watermark in this edition")
    return e


@check("L2.watermark_knockout", "BLOCKER", "No watermark ink inside or touching functional content")
def watermark_knockout(ctx: Any) -> list[Finding]:
    from PIL import ImageChops, ImageFilter

    _needs_watermark(ctx)
    out = []
    for n, (wm, ref) in enumerate(_renders(ctx), 1):
        content = ref.point(lambda v: 255 if v < 250 else 0).filter(ImageFilter.MaxFilter(7))
        diff = ImageChops.difference(wm, ref).point(lambda v: 255 if v > DIFF else 0)
        clash = ImageChops.multiply(diff, content)
        if clash.getbbox():
            out.append(
                Finding(
                    message=f"page {n}: watermark touches content at {clash.getbbox()}",
                    evidence={"page": n, "box": list(clash.getbbox() or [])},
                )
            )
    return out


@check("L2.watermark_contrast", "MAJOR", "Watermark stays faint (no dark patches, esp. grayscale)")
def watermark_contrast(ctx: Any) -> list[Finding]:
    from PIL import ImageChops

    e = _needs_watermark(ctx)
    limit = DARKEN_MAX["color" if e.get("color", True) else "gray"] * 255 + 2
    out = []
    for n, (wm, ref) in enumerate(_renders(ctx), 1):
        darkest = ImageChops.subtract(ref, wm).getextrema()[1]
        if darkest > limit:
            out.append(
                Finding(
                    message=f"page {n}: watermark darkens paper by {darkest} levels "
                    f"(max {limit:.0f})",
                    evidence={"page": n, "measured": darkest},
                )
            )
    return out


@check("L2.binding_margin", "BLOCKER", "Spiral: nothing inside the punched binding margin")
def binding_margin(ctx: Any) -> list[Finding]:
    e = edition(ctx)
    if not e or e.get("name") != "spiral":
        raise Skip("not a spiral edition")
    need = BINDING_IN[e.get("binding", "coil")] * 72
    b = bleed_in(ctx) * 72
    out = []
    for p in pdf(ctx).pages:
        if p.ink_box is None:
            continue
        x0, _, x1, _ = p.ink_box
        binding_left = not e.get("duplex", True) or p.number % 2 == 1
        room = (x0 - b) if binding_left else (p.width_pt - b - x1)
        if room < need - 1.5:
            out.append(
                Finding(
                    message=f"page {p.number}: ink {room:.0f} pt from the binding edge "
                    f"(needs {need:.0f})",
                    evidence={"page": p.number},
                )
            )
    return out


@check("L2.bleed_marks", "MAJOR", "Bleed editions: crop marks at all four trim corners")
def bleed_marks(ctx: Any) -> list[Finding]:
    import pypdfium2 as pdfium

    b = bleed_in(ctx)
    if not b:
        raise Skip("no bleed")
    doc = pdfium.PdfDocument(str(ctx.pdf_path))
    try:
        img = doc[0].render(scale=DPI / 72, grayscale=True).to_pil().convert("L")
    finally:
        doc.close()
    k = int(b * DPI)
    w, h = img.size
    corners = {
        "top-left": (0, 0),
        "top-right": (w - k, 0),
        "bottom-left": (0, h - k),
        "bottom-right": (w - k, h - k),
    }
    missing = [
        name
        for name, (x, y) in corners.items()
        if img.crop((x, y, x + k, y + k)).getextrema()[0] > 200
    ]
    return [Finding(message=f"no crop marks at {missing}")] if missing else []
