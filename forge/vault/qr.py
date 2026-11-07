"""QR codes as SVG (segno, BSD-3)."""

from __future__ import annotations

import io

import segno


def qr_svg(url: str, dark: str = "#000000") -> str:
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=10, border=2, dark=dark, xmldecl=False)
    return buf.getvalue().decode()


def solve_url(domain: str, book_id: str, code: str = "") -> str:
    base = domain if domain.startswith("http") else f"https://{domain}"
    url = f"{base.rstrip('/')}/solve/{book_id}"
    return f"{url}?code={code}" if code else url
