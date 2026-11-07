"""Certificate of a solved case: a small one-page PDF written directly (no extra dependency)."""

from __future__ import annotations


def _esc(s: str) -> str:
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _width(text: str, size: float) -> float:
    return len(text) * size * 0.5  # Helvetica average; good enough to centre short lines


def certificate_pdf(site: str, name: str, book_title: str, date: str, number: int) -> bytes:
    w, h = 792, 612  # US Letter landscape
    lines = [
        ("Helvetica-Bold", 34, 440, "Certificate of a Solved Case"),
        ("Helvetica", 16, 390, "This certifies that"),
        ("Helvetica-Bold", 26, 345, name or "A brilliant detective"),
        ("Helvetica", 16, 300, "has solved the case"),
        ("Helvetica-Bold", 22, 258, book_title),
        ("Helvetica", 13, 190, f"{date}  -  Case #{number}  -  {site}"),
    ]
    ops = ["0.12 0.31 0.47 RG 4 w 36 36 720 540 re S 1 w 46 46 700 520 re S"]
    for font, size, y, text in lines:
        f = "/F2" if font.endswith("Bold") else "/F1"
        x = max(50.0, (w - _width(text, size)) / 2)
        ops.append(f"BT {f} {size} Tf 0.1 0.1 0.1 rg {x:.1f} {y} Td ({_esc(text)}) Tj ET")
    stream = "\n".join(ops).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] "
        "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
