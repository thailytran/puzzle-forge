"""Milestone review package: review/<code>.md (checklist) + review/<code>/<book>/ (key-page PNGs,
interior.pdf, qa_report.json) so the owner can review on GitHub / Claude Code without the VM."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge.core.models import LEVEL_LABELS
from forge.qa.report import load

PNG_DPI = 72
TYPE_NAMES = {"wordsearch": "Word Search", "scramble": "Word Scramble"}

CRITERIA_COMMON = [
    "Title page: title/subtitle readable, nothing cut off",
    "How to Play: every puzzle type explained, wording clear for the audience",
    "Contents: page numbers match the pages",
    "Puzzle pages: grid centred, big enough, nothing touching the margins",
    "Difficulty label on each puzzle feels right (Beginner/Easy/Intermediate/Hard/Expert)",
    "Solutions: easy to find (#n and page number), readable when printed",
    "Overall look: fonts, spacing, header/footer, would you buy it?",
]
CRITERIA_AUDIENCE = {
    "kids_6_8": [
        "Kids 6-8: letters large, no backwards words, themes friendly, ends at Intermediate"
    ],
    "kids_9_12": ["Kids 9-12: challenge level fits the age"],
    "senior_large_print": ["Large print: every number/letter comfortably readable (≥ 16 pt)"],
    "adult": ["Adult: hard puzzles feel genuinely hard"],
}


@dataclass
class KeyPage:
    page: int
    why: str


def key_pages(manifest: dict[str, Any], layout: dict[str, Any]) -> list[KeyPage]:
    pages = layout["pages"]
    out: list[KeyPage] = [KeyPage(1, "title page")]
    for i, p in enumerate(pages, 1):
        if p.get("title") in ("How to Play", "Contents"):
            out.append(KeyPage(i, str(p["title"])))
    rows = manifest["puzzles"]
    seen: set[tuple[str, str]] = set()
    for r in rows:  # first puzzle of every (type, level)
        key = (r["type"], r["level"])
        if key not in seen:
            seen.add(key)
            name = TYPE_NAMES.get(r["type"], r["type"].title())
            out.append(KeyPage(r["page"], f"#{r['n']} {name} — {LEVEL_LABELS[r['level']]}"))
    last = rows[-1]
    out.append(KeyPage(last["page"], f"#{last['n']} last puzzle"))
    sol = sorted({r["solution_page"] for r in rows if r["solution_page"]})
    if sol:
        out.append(KeyPage(sol[0], "first solutions page"))
        out.append(KeyPage(sol[-1], "last solutions page"))
    uniq: dict[int, str] = {}
    for k in out:
        uniq.setdefault(k.page, k.why)
    return [KeyPage(p, w) for p, w in sorted(uniq.items())]


def render_pages(pdf: Path, pages: list[int], dest: Path) -> None:
    import pypdfium2 as pdfium

    dest.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    try:
        for n in pages:
            doc[n - 1].render(scale=PNG_DPI / 72).to_pil().save(
                dest / f"page-{n:03d}.png", optimize=True
            )
    finally:
        doc.close()


def pack_book(out_dir: Path, review_root: Path, code: str) -> dict[str, Any]:
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    layout = json.loads((out_dir / "layout.json").read_text(encoding="utf-8"))
    book_id = manifest["book_id"]
    dest = review_root / code / book_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    kp = key_pages(manifest, layout)
    render_pages(out_dir / "interior.pdf", [k.page for k in kp], dest)
    shutil.copy2(out_dir / "interior.pdf", dest / "interior.pdf")
    rep = load(out_dir)
    if rep:
        shutil.copy2(out_dir / "qa" / "qa_report.json", dest / "qa_report.json")
    return {"manifest": manifest, "key_pages": kp, "report": rep, "dir": dest}


def checklist(code: str, books: list[dict[str, Any]], review_root: Path) -> str:
    lines = [
        f"# Review {code}",
        "",
        "Tick `[x]` what is OK; write comments under each book. Images open directly on GitHub.",
        "",
    ]
    for i, b in enumerate(books, 1):
        m, rep = b["manifest"], b["report"]
        book = m["spec"]["book"]
        rel = b["dir"].relative_to(review_root)
        levels: dict[str, int] = {}
        for r in m["puzzles"]:
            levels[LEVEL_LABELS[r["level"]]] = levels.get(LEVEL_LABELS[r["level"]], 0) + 1
        types: dict[str, int] = {}
        for r in m["puzzles"]:
            types[r["type"]] = types.get(r["type"], 0) + 1
        qa = f"{rep.result} ({rep.counts['passed']} checks passed)" if rep else "no QA report"
        lines += [
            f"## Book {i}: {book['title']}",
            "",
            f"- Audience: `{book['audience']}` · trim {book['trim']} · {m['page_count']} pages · "
            f"{len(m['puzzles'])} puzzles",
            f"- Types: {', '.join(f'{k} {v}' for k, v in types.items())}",
            f"- Levels: {', '.join(f'{k} {v}' for k, v in levels.items())}",
            f"- QA: **{qa}** · full PDF: [{rel}/interior.pdf]({rel}/interior.pdf)",
            "",
            "Pages to look at:",
            "",
        ]
        for k in b["key_pages"]:
            lines.append(f"- [ ] p.{k.page} — {k.why}: [image]({rel}/page-{k.page:03d}.png)")
        lines += ["", "Criteria:", ""]
        crit = CRITERIA_COMMON + CRITERIA_AUDIENCE.get(book["audience"], [])
        lines += [f"- [ ] {c}" for c in crit]
        lines += ["", "Comments:", "", "> ", ""]
    return "\n".join(lines)


def make_review(code: str, out_dirs: list[Path], review_root: Path) -> Path:
    books = [pack_book(d, review_root, code) for d in out_dirs]
    md = review_root / f"{code}.md"
    md.write_text(checklist(code, books, review_root), encoding="utf-8")
    return md
