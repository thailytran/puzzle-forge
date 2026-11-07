"""Per-order personalisation of a QA'd DIGITAL master (stamp) and order tracing (trace).

The stamp is an overlay merged onto every page of the master (pypdf, BSD): the master's own content
is untouched, so `verify_stamp` can prove that only the approved stamp band differs. Layers:
  1. footer line "Licensed to <buyer> • Order #<order> • Personal use only" in the reserved band,
  2. PDF metadata (/ForgeOrder, buyer + e-mail hashes),
  3. a micro-pattern: 40 faint dots in the band encoding the order number (32 bits) + checksum (8),
  4. permissions: print allowed, edits not (owner password).
These are deterrents only: metadata, permissions and overlays can be stripped by a determined user.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.constants import UserAccessPermissions

from forge.layout.typst_runner import compile_pdf

BITS = 40
DOT_PT = 1.6
DOT_STEP_PT = 4.0
DOT_X0_IN = 0.55  # from the left edge
BAND_Y_IN = 0.16  # dot centre / text baseline height above the bottom edge
ZONE_IN = 0.32  # approved stamp band: bottom 0.32" of every page
DOT_GRAY = 0.82  # dot luminance (1 = white): faint, still read back at 300 dpi


@dataclass(frozen=True)
class Order:
    buyer: str
    order: int
    email: str = ""


def _checksum(order: int) -> int:
    return hashlib.sha256(str(order).encode()).digest()[0]


def encode_bits(order: int) -> list[int]:
    if not 0 <= order < 2**32:
        raise ValueError("order number must fit in 32 bits")
    value = (order << 8) | _checksum(order)
    return [(value >> (BITS - 1 - i)) & 1 for i in range(BITS)]


def decode_bits(bits: list[int]) -> int | None:
    value = 0
    for b in bits:
        value = (value << 1) | b
    order, check = value >> 8, value & 0xFF
    return order if _checksum(order) == check else None


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def overlay_typst(o: Order, width_pt: float, height_pt: float, pages: int) -> str:
    dots = "".join(
        f"place(bottom + left, dx: {DOT_X0_IN}in + {i * DOT_STEP_PT}pt - {DOT_PT / 2}pt, "
        f"dy: -{BAND_Y_IN}in + {DOT_PT / 2}pt, "
        f"square(size: {DOT_PT}pt, fill: luma({DOT_GRAY * 100}%)))\n"
        for i, bit in enumerate(encode_bits(o.order))
        if bit
    )
    line = f"Licensed to {o.buyer} • Order #{o.order} • Personal use only"
    return f"""#set page(width: {width_pt}pt, height: {height_pt}pt, margin: 0pt)
#set text(font: "Atkinson Hyperlegible", size: 6.5pt, fill: luma(35%))
#let stamp = {{
place(bottom + center, dy: -{BAND_Y_IN}in + 2.2pt, text("{_esc(line)}"))
{dots}}}
#for i in range({pages}) {{ page(stamp) }}
"""


def make_overlay(o: Order, width_pt: float, height_pt: float, pages: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        main = Path(tmp) / "stamp.typ"
        main.write_text(overlay_typst(o, width_pt, height_pt, pages), encoding="utf-8")
        return compile_pdf(main, Path(tmp) / "stamp.pdf").read_bytes()


def stamp_pdf(master: Path, out: Path, o: Order) -> Path:
    reader = PdfReader(master)
    box = reader.pages[0].mediabox
    overlay = PdfReader(
        io.BytesIO(make_overlay(o, float(box.width), float(box.height), len(reader.pages)))
    )
    writer = PdfWriter(clone_from=reader)
    for page, ov in zip(writer.pages, overlay.pages, strict=True):
        page.merge_page(ov)
    writer.add_metadata(
        {
            "/ForgeOrder": str(o.order),
            "/ForgeBuyer": hashlib.sha256(o.buyer.encode()).hexdigest()[:16],
            "/ForgeEmail": hashlib.sha256(o.email.lower().encode()).hexdigest()[:16]
            if o.email
            else "",
            "/Subject": f"Licensed copy, order #{o.order}",
        }
    )
    writer.encrypt(
        user_password="",
        owner_password=secrets.token_hex(16),
        algorithm="AES-128",
        permissions_flag=UserAccessPermissions.PRINT
        | UserAccessPermissions.PRINT_TO_REPRESENTATION,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        writer.write(fh)
    return out


def _render(pdf: Path, dpi: int) -> list[object]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf), password="")
    try:
        return [
            doc[i].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
            for i in range(len(doc))
        ]
    finally:
        doc.close()


def verify_stamp(master: Path, stamped: Path, dpi: int = 72) -> list[str]:
    """Problems (empty = OK): the stamped copy may differ from the master only in the stamp band."""
    from PIL import ImageChops

    a, b = _render(master, dpi), _render(stamped, dpi)
    if len(a) != len(b):
        return [f"page count {len(b)} != master {len(a)}"]
    out = []
    for n, (pa, pb) in enumerate(zip(a, b, strict=True), 1):
        if pa.size != pb.size:  # type: ignore[attr-defined]
            out.append(f"page {n}: size differs")
            continue
        diff = ImageChops.difference(pa, pb).point(lambda v: 255 if v > 3 else 0)  # type: ignore[arg-type]
        band = int(ZONE_IN * dpi)
        outside = diff.crop((0, 0, diff.width, diff.height - band))
        if outside.getbbox():
            out.append(f"page {n}: changed outside the stamp band at {outside.getbbox()}")
    return out


def trace_pdf(pdf: Path) -> dict[str, object]:
    """Read the order number back from metadata and from the micro-pattern (page 1)."""
    reader = PdfReader(pdf)
    if reader.is_encrypted:
        reader.decrypt("")
    meta = reader.metadata or {}
    img = _render(pdf, 300)[0]
    scale = 300 / 72
    y = img.height - BAND_Y_IN * 300  # type: ignore[attr-defined]
    bits = []
    for i in range(BITS):
        x = DOT_X0_IN * 300 + i * DOT_STEP_PT * scale
        px = img.getpixel((round(x), round(y)))  # type: ignore[attr-defined]
        bits.append(1 if px < 230 else 0)
    return {
        "metadata_order": meta.get("/ForgeOrder"),
        "pattern_order": decode_bits(bits),
        "bits": "".join(map(str, bits)),
    }


def stamp_book(out_dir: Path, o: Order) -> list[Path]:
    """Stamp every QA_PASSED digital master of a book into output/<book>/orders/<order>/."""
    from forge.qa.report import report_valid

    masters = sorted(p for p in (out_dir / "editions").glob("digital-*") if p.is_dir())
    if not masters:
        raise FileNotFoundError("no digital edition: run `forge edition build --edition digital`")
    done = []
    for ed in masters:
        if not report_valid(ed):
            raise PermissionError(f"{ed.name}: master is not QA_PASSED (run `forge qa run {ed}`)")
        dest = out_dir / "orders" / str(o.order) / f"{out_dir.name}-{ed.name}-order{o.order}.pdf"
        stamp_pdf(ed / "interior.pdf", dest, o)
        problems = verify_stamp(ed / "interior.pdf", dest)
        if problems:
            dest.unlink()
            raise ValueError(f"{ed.name}: stamped copy rejected (L2.stamp_diff): {problems[:3]}")
        (dest.parent / "order.json").write_text(
            json.dumps(
                {"order": o.order, "buyer": o.buyer, "files": [p.name for p in [*done, dest]]},
                indent=1,
            ),
            encoding="utf-8",
        )
        done.append(dest)
    return done
