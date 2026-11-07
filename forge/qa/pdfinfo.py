"""Facts measured from the rendered interior.pdf (pypdfium2: Apache-2.0/BSD-3, PDFium BSD-3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

DPI = 72  # 1 px = 1 pt
INK = 200  # grayscale below this counts as ink


@dataclass
class PageFacts:
    number: int  # 1-based physical page
    width_pt: float
    height_pt: float
    text: str
    ink_box: tuple[int, int, int, int] | None  # left, top, right, bottom (pt from top-left)
    body_ink: bool  # ink outside the header/footer zones
    chars: list[tuple[str, float, float, float]] = field(default_factory=list)  # ch, size, x, y_top
    images: list[tuple[float, float]] = field(default_factory=list)  # effective dpi (x, y)

    @property
    def compact(self) -> str:
        return "".join(self.text.split())


class PdfFacts:
    def __init__(self, path: Path, header_zone_pt: float = 36.0, bleed_pt: float = 0.0) -> None:
        self.path = path
        self.header_zone_pt = header_zone_pt
        self.bleed_pt = bleed_pt

    @cached_property
    def pages(self) -> list[PageFacts]:
        import pypdfium2 as pdfium
        import pypdfium2.raw as raw

        doc = pdfium.PdfDocument(str(self.path))
        out: list[PageFacts] = []
        try:
            for i in range(len(doc)):
                page = doc[i]
                w, h = page.get_size()
                tp = page.get_textpage()
                text = tp.get_text_range()
                chars: list[tuple[str, float, float, float]] = []
                for k in range(tp.count_chars()):
                    ch = chr(raw.FPDFText_GetUnicode(tp.raw, k))
                    if ch.isspace():
                        continue
                    size = float(raw.FPDFText_GetFontSize(tp.raw, k))
                    left, _bottom, _right, top = tp.get_charbox(k)
                    chars.append((ch, size, left, h - top))
                img = page.render(scale=DPI / 72, grayscale=True).to_pil()
                mask = img.point(lambda v: 255 if v < INK else 0)
                b = int(self.bleed_pt)
                if b:  # measure inside the trim box only (crop marks sit in the bleed)
                    from PIL import Image

                    trimmed = Image.new("L", mask.size, 0)
                    trimmed.paste(mask.crop((b, b, mask.width - b, mask.height - b)), (b, b))
                    mask = trimmed
                box = mask.getbbox()
                zone = int(self.header_zone_pt)
                body = mask.crop((0, zone, mask.width, mask.height - zone)).getbbox()
                images = []
                for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=3):
                    px_w, px_h = obj.get_size()
                    x0, y0, x1, y1 = obj.get_pos()
                    if x1 > x0 and y1 > y0:
                        images.append((px_w / ((x1 - x0) / 72), px_h / ((y1 - y0) / 72)))
                out.append(PageFacts(i + 1, w, h, text, box, body is not None, chars, images))
        finally:
            doc.close()
        return out

    def font_report(self) -> list[tuple[int, str, bool]]:
        """(page, font name, embedded) for every font resource (pypdf)."""
        from pypdf import PdfReader

        rows: list[tuple[int, str, bool]] = []
        for i, page in enumerate(PdfReader(self.path).pages, 1):
            fonts = page.get("/Resources", {}).get("/Font", {})
            for ref in fonts.values():
                f = ref.get_object()
                desc = f.get("/FontDescriptor")
                if desc is None and "/DescendantFonts" in f:
                    desc = f["/DescendantFonts"][0].get_object().get("/FontDescriptor")
                desc = desc.get_object() if desc is not None else {}
                embedded = any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
                if f.get("/Subtype") == "/Type3":
                    embedded = True  # glyphs are drawn inline
                rows.append((i, str(f.get("/BaseFont")), embedded))
        return rows

    def thumbnails(self, out_dir: Path, dpi: int = 40) -> int:
        import pypdfium2 as pdfium

        out_dir.mkdir(parents=True, exist_ok=True)
        doc = pdfium.PdfDocument(str(self.path))
        try:
            for i in range(len(doc)):
                doc[i].render(scale=dpi / 72).to_pil().save(out_dir / f"page-{i + 1:03d}.png")
            return len(doc)
        finally:
            doc.close()
