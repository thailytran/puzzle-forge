"""Book Code batches: CSV (plaintext, stays on this machine) + one code page per printed copy."""

from __future__ import annotations

import csv
import secrets
from datetime import UTC, datetime
from pathlib import Path

from forge.vault import bookcode

CODES_DIR = Path("vault") / "codes"
CHANNELS = ("print", "shopify_digital")


def make_batch(out_dir: Path, count: int, channel: str, batch_id: str | None = None) -> Path:
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    if not 1 <= count <= 100_000:
        raise ValueError("count must be 1..100000")
    bid = batch_id or f"{channel}-{datetime.now(UTC):%Y%m%d%H%M%S}"
    d = out_dir / CODES_DIR
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{bid}.csv"
    if path.exists():
        raise FileExistsError(f"batch {bid} exists")
    rng = secrets.SystemRandom()
    codes: set[str] = set()
    while len(codes) < count:
        codes.add(bookcode.new_code(rng))
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "pretty", "batch_id", "channel"])
        for c in sorted(codes):
            w.writerow([c, bookcode.pretty(c), bid, channel])
    return path


def read_batches(out_dir: Path) -> list[dict[str, object]]:
    out = []
    for p in sorted((out_dir / CODES_DIR).glob("*.csv")):
        with p.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if rows:
            out.append(
                {
                    "batch_id": rows[0]["batch_id"],
                    "channel": rows[0]["channel"],
                    "codes": [r["code"] for r in rows],
                }
            )
    return out


def code_pages_pdf(out_dir: Path, batch_csv: Path, domain: str, trim: str = "") -> Path:
    """Variable-data PDF: one page per code (QR to /solve/<book_id>?code=… + the code in text).
    Printed and inserted into each physical copy (spiral / direct sale / gift)."""
    import json
    import tempfile

    from forge.layout.trim import TRIMS
    from forge.layout.typst_runner import compile_pdf
    from forge.vault.qr import qr_svg, solve_url

    if not domain:
        raise ValueError("VAULT_DOMAIN must be set in .env (printed on every code page)")
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    bid = str(manifest["book_id"])
    t = TRIMS[trim or manifest["spec"]["book"].get("trim", "8.5x11")]
    with batch_csv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    site = domain.removeprefix("https://").removeprefix("http://").rstrip("/")
    with tempfile.TemporaryDirectory() as tmp:
        pages = []
        for i, r in enumerate(rows):
            (Path(tmp) / f"q{i}.svg").write_text(qr_svg(solve_url(domain, bid, r["code"])))
            pages.append(
                f'#page[#align(center + horizon)[#text(20pt, weight: "bold")[Your Book Code]\n'
                f'#v(10pt)\n#image("q{i}.svg", width: 2.2in)\n#v(10pt)\n'
                f'#text(font: "Courier Prime", 22pt, weight: "bold")[{r["pretty"]}]\n#v(8pt)\n'
                f"#text(11pt)[Solved the case? Scan the code or visit]\n\n"
                f'#box(text(12pt, weight: "bold")[{site}/solve/{bid}])\n\n'
                f"#text(11pt)[and enter this code to unlock your rewards.]\n"
                f"#v(4pt)\n#text(9pt, fill: luma(40%))[One code per book. Keep it private.]]]"
            )
        main = Path(tmp) / "codes.typ"
        main.write_text(
            f"#set page(width: {t.width_in}in, height: {t.height_in}in, margin: 0.75in)\n"
            '#set text(font: "Atkinson Hyperlegible")\n' + "\n".join(pages),
            encoding="utf-8",
        )
        out = batch_csv.with_suffix(".pdf")
        compile_pdf(main, out)
    return out
