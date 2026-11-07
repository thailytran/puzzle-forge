"""Render an edition (digital / spiral) of an already built + verified book."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from forge.book.builder import layout_book, load_puzzles, manifest
from forge.core.book import BookSpec
from forge.editions.brand import art_files, load_brand
from forge.editions.settings import EditionSettings
from forge.layout.document import render_pdf

NOWM_PDF = "interior_nowm.pdf"  # same layout without watermark: QA reference for knock-out checks


def edition_dir(out_dir: Path, ed: EditionSettings) -> Path:
    return out_dir / "editions" / ed.label


def build_edition(out_dir: Path, ed: EditionSettings) -> Path:
    base = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    spec = BookSpec.model_validate(base["spec"])
    puzzles = load_puzzles(out_dir)
    built = layout_book(spec, puzzles, edition=ed)
    built = layout_book(spec, puzzles, est_pages=len(built.doc.pages), edition=ed)
    dest = edition_dir(out_dir, ed)
    dest.mkdir(parents=True, exist_ok=True)
    man = manifest(spec, base["book_id"], puzzles, built)
    man["book_id"] = f"{base['book_id']}@{ed.label}"
    man["base_book_id"] = base["book_id"]
    man["trim"] = ed.trim or spec.book.trim
    man["edition"] = ed.model_dump()
    (dest / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    (dest / "layout.json").write_text(built.doc.to_json(), encoding="utf-8")
    shutil.copy2(out_dir / "puzzles.jsonl", dest / "puzzles.jsonl")
    files = {**built.files, **art_files(load_brand(), ed.color)}
    pdf = render_pdf(built.doc, dest / "interior.pdf", files=files)
    if ed.watermark:
        ref = built.doc.model_copy(
            update={"edition": {**(built.doc.edition or {}), "watermark": False}}
        )
        render_pdf(ref, dest / "build_nowm" / NOWM_PDF, files=files)
        shutil.move(dest / "build_nowm" / NOWM_PDF, dest / NOWM_PDF)
    return pdf
