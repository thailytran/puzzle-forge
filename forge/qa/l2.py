"""L2 — per-page checks on the rendered PDF, and L1.print_roundtrip ("printed = verified")."""

from __future__ import annotations

import json
import re
from typing import Any

from forge.core.models import Puzzle
from forge.layout.trim import TRIMS, gutter_for, load_kdp_rules
from forge.qa.checks import Finding, check
from forge.qa.pdfinfo import PdfFacts

TOL_PT = 1.5
MIN_TEXT_PT = {"senior_large_print": 16.0, "kids_6_8": 11.0}
MIN_CELL_IN = {"senior_large_print": 0.4, "kids_6_8": 0.45}
GRID_BLOCKS = ("letter_grid", "sudoku_grid", "crossword_grid")
SIZE_EXEMPT_KINDS = ("solutions", "title", "notes", "blank")
TYPE_NAMES = {"wordsearch": "Word Search", "scramble": "Word Scramble"}


def pdf(ctx: Any) -> PdfFacts:
    if "pdf" not in ctx.extra:
        if not ctx.pdf_path.is_file():
            raise FileNotFoundError("interior.pdf missing — build with rendering")
        ctx.extra["pdf"] = PdfFacts(ctx.pdf_path)
    return ctx.extra["pdf"]  # type: ignore[no-any-return]


def layout(ctx: Any) -> dict[str, Any]:
    if "layout" not in ctx.extra:
        ctx.extra["layout"] = json.loads((ctx.out_dir / "layout.json").read_text(encoding="utf-8"))
    return ctx.extra["layout"]  # type: ignore[no-any-return]


def _audience(ctx: Any) -> str:
    return str(ctx.manifest["spec"]["book"]["audience"])


@check("L2.trim", "BLOCKER", "Every page has the trim size of the spec")
def trim(ctx: Any) -> list[Finding]:
    t = TRIMS[ctx.manifest["trim"]]
    out = []
    for p in pdf(ctx).pages:
        if abs(p.width_pt - t.width_in * 72) > 0.5 or abs(p.height_pt - t.height_in * 72) > 0.5:
            out.append(
                Finding(
                    message=f"page {p.number}: {p.width_pt}x{p.height_pt} pt",
                    evidence={
                        "page": p.number,
                        "measured": [p.width_pt, p.height_pt],
                        "expected": [t.width_in * 72, t.height_in * 72],
                    },
                )
            )
    return out


@check("L2.safe_area", "BLOCKER", "All ink inside KDP minimum margins (gutter by page count)")
def safe_area(ctx: Any) -> list[Finding]:
    pages = pdf(ctx).pages
    rules = load_kdp_rules()
    inside = gutter_for(len(pages)) * 72
    edge = rules.outside_min_in * 72
    out = []
    for p in pages:
        if p.ink_box is None:
            continue
        left_min = inside if p.number % 2 == 1 else edge  # recto: gutter on the left
        right_min = edge if p.number % 2 == 1 else inside
        x0, y0, x1, y1 = p.ink_box
        bad = []
        if x0 < left_min - TOL_PT:
            bad.append(f"left {x0:.0f} < {left_min:.0f}")
        if p.width_pt - x1 < right_min - TOL_PT:
            bad.append(f"right {p.width_pt - x1:.0f} < {right_min:.0f}")
        if y0 < edge - TOL_PT:
            bad.append(f"top {y0:.0f} < {edge:.0f}")
        if p.height_pt - y1 < edge - TOL_PT:
            bad.append(f"bottom {p.height_pt - y1:.0f} < {edge:.0f}")
        if bad:
            out.append(
                Finding(
                    message=f"page {p.number}: ink outside margins ({', '.join(bad)} pt)",
                    evidence={"page": p.number, "ink_box": list(p.ink_box)},
                )
            )
    return out


@check("L2.fonts_embedded", "BLOCKER", "Every font is embedded")
def fonts_embedded(ctx: Any) -> list[Finding]:
    return [
        Finding(message=f"page {pg}: font {name} not embedded", evidence={"page": pg, "font": name})
        for pg, name, emb in pdf(ctx).font_report()
        if not emb
    ]


@check("L2.min_sizes", "MAJOR", "Minimum text and cell sizes for the audience")
def min_sizes(ctx: Any) -> list[Finding]:
    aud = _audience(ctx)
    out: list[Finding] = []
    min_pt = MIN_TEXT_PT.get(aud)
    min_cell = MIN_CELL_IN.get(aud)
    pages_layout = layout(ctx)["pages"]
    zone = pdf(ctx).header_zone_pt
    for p, lp in zip(pdf(ctx).pages, pages_layout, strict=False):
        if lp["kind"] in SIZE_EXEMPT_KINDS:
            continue
        if min_pt:
            small = [
                c
                for c in p.chars
                if c[1] > 1.5 and c[1] < min_pt - 0.2 and zone < c[3] < p.height_pt - zone
            ]
            if small:
                out.append(
                    Finding(
                        message=f"page {p.number}: {len(small)} chars below {min_pt} pt "
                        f"(smallest {min(c[1] for c in small):.1f} pt)",
                        evidence={
                            "page": p.number,
                            "min_pt": min_pt,
                            "sample": "".join(c[0] for c in small[:20]),
                        },
                    )
                )
        if min_cell:
            for b in lp["blocks"]:
                if b.get("kind") in GRID_BLOCKS and b.get("cell_in", 1) < min_cell - 1e-6:
                    out.append(
                        Finding(
                            message=f'page {p.number}: grid cell {b["cell_in"]}" < {min_cell}"',
                            evidence={"page": p.number, "cell_in": b["cell_in"]},
                        )
                    )
    return out


@check("L2.image_dpi", "BLOCKER", "Raster images at least 300 effective DPI")
def image_dpi(ctx: Any) -> list[Finding]:
    return [
        Finding(
            message=f"page {p.number}: image at {min(d):.0f} DPI",
            evidence={"page": p.number, "dpi": list(d)},
        )
        for p in pdf(ctx).pages
        for d in p.images
        if min(d) < 300 - 1
    ]


def _footer_number(p: Any, zone: float) -> str:
    digits = [c for c in p.chars if c[3] > p.height_pt - zone and c[0].isdigit()]
    return "".join(c[0] for c in sorted(digits, key=lambda c: c[2]))


@check("L2.page_numbers", "MAJOR", "Printed page numbers are continuous")
def page_numbers(ctx: Any) -> list[Finding]:
    out = []
    zone = pdf(ctx).header_zone_pt
    for p, lp in zip(pdf(ctx).pages, layout(ctx)["pages"], strict=False):
        if not lp.get("number", True) or lp["kind"] == "title":
            continue
        got = _footer_number(p, zone)
        if got != str(p.number):
            out.append(
                Finding(
                    message=f"page {p.number}: footer shows {got!r}",
                    evidence={"page": p.number, "printed": got},
                )
            )
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


@check("L2.solution_match", "BLOCKER", "Puzzle #n and solution #n are the same puzzle")
def solution_match(ctx: Any) -> list[Finding]:
    pages = pdf(ctx).pages
    out = []
    for row in ctx.manifest["puzzles"]:
        n, page, sol = row["n"], row["page"], row["solution_page"]
        if f"#{n} " not in _norm(pages[page - 1].text):
            out.append(
                Finding(
                    message=f"#{n}: title not found on page {page}",
                    evidence={"puzzle_id": row["id"], "page": page},
                )
            )
        if sol is None:
            out.append(
                Finding(message=f"#{n}: no solution page", evidence={"puzzle_id": row["id"]})
            )
        elif f"#{n} (page {page})" not in _norm(pages[sol - 1].text):
            out.append(
                Finding(
                    message=f"#{n}: solution on page {sol} does not point to page {page}",
                    evidence={"puzzle_id": row["id"], "page": page, "solution_page": sol},
                )
            )
    return out


@check("L2.instructions", "MAJOR", "A how-to-play text exists for every puzzle type used")
def instructions(ctx: Any) -> list[Finding]:
    texts = [_norm(p.text) for p in pdf(ctx).pages]
    how = next((t for t in texts if "How to Play" in t), None)
    types = sorted({r["type"] for r in ctx.manifest["puzzles"]})
    if how is None:
        return [Finding(message="no How to Play page", evidence={"types": types})]
    missing = [t for t in types if TYPE_NAMES.get(t, t.title()) not in how]
    return (
        [Finding(message=f"How to Play misses {missing}", evidence={"missing": missing})]
        if missing
        else []
    )


@check("L2.no_unintended_blank", "MAJOR", "No blank page except declared blank pages")
def no_blank(ctx: Any) -> list[Finding]:
    return [
        Finding(message=f"page {p.number} ({lp['kind']}) is blank", evidence={"page": p.number})
        for p, lp in zip(pdf(ctx).pages, layout(ctx)["pages"], strict=False)
        if not p.body_ink and lp["kind"] != "blank"
    ]


@check("L2.thumbnails", "MINOR", "PNG thumbnail of every page in previews/")
def thumbnails(ctx: Any) -> list[Finding]:
    n = pdf(ctx).thumbnails(ctx.out_dir / "previews")
    total = len(pdf(ctx).pages)
    return [] if n == total else [Finding(message=f"{n}/{total} thumbnails written")]


@check("L2.page_count_match", "BLOCKER", "PDF page count equals the planned layout (no overflow)")
def page_count_match(ctx: Any) -> list[Finding]:
    got, want = len(pdf(ctx).pages), len(layout(ctx)["pages"])
    return (
        []
        if got == want
        else [
            Finding(
                message=f"PDF has {got} pages, layout planned {want}",
                evidence={"measured": got, "expected": want},
            )
        ]
    )


# ------------------------------------------------------------------ printed = verified


def _subsequence(needle: str, hay: str) -> bool:
    it = iter(hay)
    return all(ch in it for ch in needle)


def _expected(p: Puzzle) -> tuple[list[str], list[str]]:
    """(substrings that must appear, sequences that must appear in order) — whitespace-free."""
    d = p.data
    if p.type == "wordsearch":
        return ["".join(r.replace(".", "") for r in d["rows"]), *d["words"]], []
    if p.type == "sudoku":
        return ["".join(str(v) for row in d["givens"] for v in row if v)], []
    if p.type == "crossword":
        return list(d["words"]), [
            "".join(
                d["givens"][k]
                for k in sorted(d["givens"], key=lambda k: tuple(map(int, k.split(","))))
            )
        ]
    if p.type == "scramble":
        return [*d["items"], *([d["bonus"]] if d.get("bonus") else [])], []
    if p.type == "cryptogram":
        letters = "".join(ch for ch in d["cipher"] if ch.isalpha())
        return [], [letters]
    if p.type == "maze":
        return [], ["".join(x["ch"] for x in d.get("letters", []))]
    return [], []


@check(
    "L1.print_roundtrip", "BLOCKER", "Puzzle data read back from the PDF matches the verified data"
)
def print_roundtrip(ctx: Any) -> list[Finding]:
    pages = pdf(ctx).pages
    out = []
    for n, (pz, row) in enumerate(zip(ctx.puzzles, ctx.manifest["puzzles"], strict=True), 1):
        text = pages[row["page"] - 1].compact
        subs, seqs = _expected(pz)
        missing = [s for s in subs if s and s not in text] + [
            s for s in seqs if s and not _subsequence(s, text)
        ]
        if pz.type == "maze":
            from forge.puzzles.maze.render import svg

            img = ctx.out_dir / "build" / "img" / f"{pz.id}.svg"
            if not img.is_file() or img.read_bytes() != svg(pz, with_route=False):
                missing.append("maze SVG differs from the verified maze")
        if missing:
            out.append(
                Finding(
                    message=f"#{n} page {row['page']}: printed content differs",
                    evidence={
                        "puzzle_id": pz.id,
                        "page": row["page"],
                        "missing": [m[:40] for m in missing],
                    },
                )
            )
    return out
