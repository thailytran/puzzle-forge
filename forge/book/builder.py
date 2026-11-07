"""Build a classic book: generate every planned puzzle (verified + catalog-unique), lay out pages,
render interior.pdf and write manifest.json + puzzles.jsonl."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from forge import __version__
from forge.book.content_plan import (
    ILLUSTRATIONS_FILE,
    PLAN_FILE,
    ContentPlan,
    illustration_requests,
    load_plan,
    save_plan,
    validate_plan,
)
from forge.book.plan import Slot, plan_book, theme_rotation
from forge.book.texts import ABOUT, COPYRIGHT, HOW_TO_PLAY, THANK_YOU
from forge.core.book import BookSpec
from forge.core.models import LEVEL_LABELS, LEVELS, Puzzle, PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.core.registry import Registry
from forge.core.seeds import derive_seed
from forge.editions.settings import EditionSettings
from forge.layout.document import LayoutDoc, Page, make_layout
from forge.layout.trim import TRIMS, margins_for
from forge.puzzles.base import GenerationError
from forge.puzzles.registry import get_puzzle_type
from forge.qa.l1 import band_ok

MAX_SEED_TRIES = 30
MAX_ALT_THEMES = 4
TITLE_SPACE_IN = 0.9
SOLUTION_TITLE_IN = 0.35


class BuildError(RuntimeError):
    pass


def book_id_for(spec: BookSpec) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", spec.book.title.lower()).strip("-")[:40]
    return f"{slug}-{spec.book.seed}"


def puzzle_seed(spec: BookSpec, slot: Slot, attempt: int) -> int:
    return derive_seed(spec.book.seed, "puzzle", slot.index, attempt)


def generate_puzzles(
    spec: BookSpec,
    book_id: str,
    registry: Registry,
    offsets: dict[int, int] | None = None,
    plan: ContentPlan | None = None,
) -> list[Puzzle]:
    """`offsets[slot]` shifts the seed attempts of a slot (used by the QA auto-fixer)."""
    offsets = offsets or {}
    themes = theme_rotation(spec)
    used_quotes: set[str] = set()
    out: list[Puzzle] = []
    seen: set[str] = set()
    for slot in plan_book(spec):
        pt = get_puzzle_type(slot.type)
        opts = dict(slot.options)
        if slot.type == "cryptogram" and used_quotes:
            opts["exclude"] = sorted(used_quotes)  # no quote twice in one book
        page = plan.page(slot.index + 1) if plan else None
        page_words: list[str] | None = None
        theme = slot.theme
        if page is not None:  # content plan: the page's own sub-theme, words and quotes
            theme = page.subtheme
            page_words = list(page.words) or None
            if page.quotes:
                opts["quotes"] = [q.model_dump() for q in page.quotes]
        ps = PuzzleSpec(
            type=slot.type,
            level=slot.level,
            audience=spec.book.audience,
            theme=theme,
            words=page_words,
            options=opts,
        )
        last: Exception | None = None
        best: tuple[int, Puzzle] | None = None
        candidates = [ps]
        if slot.theme is not None and page is None:  # no plan: other themes may reach the level
            rot = [t for t in themes if t != slot.theme]
            candidates += [ps.model_copy(update={"theme": t}) for t in rot[:MAX_ALT_THEMES]]
        tries = [(c, a) for c in candidates for a in range(MAX_SEED_TRIES)]
        for ps_try, attempt in tries:
            if best is not None and best[0] == 0:
                break
            try:
                pz = pt.generate(
                    ps_try,
                    puzzle_seed(spec, slot, attempt + offsets.get(slot.index, 0))
                    if ps_try.theme == ps.theme
                    else derive_seed(spec.book.seed, "alt", slot.index, ps_try.theme, attempt),
                )
            except GenerationError as exc:
                last = exc
                continue
            if pz.content_hash in seen or registry.owner(pz.content_hash) not in (None, book_id):
                last = GenerationError(f"duplicate {pz.id}")
                continue
            label = pz.difficulty.label if pz.difficulty else slot.level
            dist = (
                0
                if band_ok(slot.level, label, ps.audience)
                else abs(LEVELS.index(label) - LEVELS.index(slot.level))
            )
            if best is None or dist < best[0]:
                best = (dist, pz)
        if best is None:
            raise BuildError(f"puzzle #{slot.index + 1} ({slot.type}, {slot.level}): {last}")
        pz = best[1]  # closest band if no exact match: QA L1.difficulty_band will report it
        registry.add(pz, book_id)
        if pz.type == "cryptogram":
            from forge.puzzles.cryptogram import quote_id

            used_quotes.update(quote_id(q["plain"]) for q in pz.solution["quotes"])
        seen.add(pz.content_hash)
        out.append(pz)
    return out


@dataclass
class Built:
    doc: LayoutDoc
    files: dict[str, bytes] = field(default_factory=dict)
    puzzle_pages: dict[str, int] = field(default_factory=dict)  # puzzle_id -> page number
    solution_pages: dict[str, int] = field(default_factory=dict)


def _geometry(
    spec: BookSpec, page_count: int, edition: EditionSettings | None
) -> tuple[str, dict[str, float]]:
    """(trim, margins) for the KDP interior or an edition."""
    trim = (edition.trim if edition else None) or spec.book.trim
    k = margins_for(page_count)
    kdp = {"inside": k.inside, "outside": k.outside, "top": k.top, "bottom": k.bottom}
    return trim, edition.margins(kdp) if edition else kdp


def _ctx(
    spec: BookSpec,
    page_count: int,
    w_share: float = 1.0,
    h: float | None = None,
    edition: EditionSettings | None = None,
) -> RenderCtx:
    trim, m = _geometry(spec, page_count, edition)
    t = TRIMS[trim]
    width = (t.width_in - m["inside"] - m["outside"]) * w_share
    height = h if h is not None else t.height_in - m["top"] - m["bottom"] - TITLE_SPACE_IN
    return RenderCtx(width_in=width, height_in=height, large_print=spec.book.large_print)


def _title(n: int, pz: Puzzle) -> str:
    label = LEVEL_LABELS[pz.spec.level]
    theme = f": {pz.spec.theme.replace('_', ' ').title()}" if pz.spec.theme else ""
    name = {"wordsearch": "Word Search", "scramble": "Word Scramble", "cbn": "Color by Number"}.get(
        pz.type, pz.type.title()
    )
    return f"#{n} {name}{theme} ({label})"


def licence_lines(edition: EditionSettings | None) -> list[str]:
    """Copyright & licence terms for digital / spiral editions (brand config)."""
    if edition is None or edition.name == "kdp":
        return []
    from forge.editions.brand import load_brand

    b = load_brand()
    lines = [f"Licence: {b.license_line} © {b.year} {b.name} • {b.website}"]
    if edition.name == "digital":
        lines.append(
            "This PDF is licensed to one buyer for personal use. Do not share, upload, "
            "sell or redistribute it."
        )
    if edition.name == "spiral" and b.classroom_copy_allowed:
        lines.append(
            "Owners of this printed edition may photocopy pages for use within their own "
            "family or classroom. Any other copying, sharing or resale is not permitted."
        )
    return lines


def layout_book(
    spec: BookSpec,
    puzzles: list[Puzzle],
    est_pages: int = 150,
    edition: EditionSettings | None = None,
) -> Built:
    b = spec.book
    built = Built(doc=make_layout(title=b.title, trim=b.trim, pages=[], min_pages=0))
    types_used = list(dict.fromkeys(p.type for p in puzzles))
    front: list[Page] = []
    toc_index: int | None = None
    for item in spec.front_matter:
        if item == "title":
            front.append(Page(kind="title"))
        elif item == "copyright":
            text = COPYRIGHT.format(year=date.today().year, author=b.author)
            front.append(
                Page(
                    kind="copyright",
                    header=False,
                    blocks=[
                        {"kind": "spacer", "height_in": 4.0},
                        {"kind": "paragraph", "text": text},
                        *[{"kind": "paragraph", "text": t} for t in licence_lines(edition)],
                    ],
                )
            )
        elif item == "how_to_play":
            blocks: list[dict[str, Any]] = []
            for t in types_used:
                name = {
                    "wordsearch": "Word Search",
                    "scramble": "Word Scramble",
                    "cbn": "Color by Number",
                }.get(t, t.title())
                blocks += [
                    {"kind": "heading", "level": 2, "text": name},
                    {"kind": "paragraph", "text": HOW_TO_PLAY.get(t, "")},
                ]
            front.append(Page(kind="text", title="How to Play", blocks=blocks))
        elif item == "table_of_contents":
            toc_index = len(front)
            front.append(Page(kind="text", title="Contents", blocks=[]))
    pages = list(front)
    ctx = _ctx(spec, est_pages, edition=edition)
    for n, pz in enumerate(puzzles, 1):
        rb = get_puzzle_type(pz.type).render(pz, ctx)
        built.files.update(rb.files)
        pages.append(Page(kind="puzzle", title=_title(n, pz), blocks=rb.blocks))
        built.puzzle_pages[pz.id] = len(pages)
    first_puzzle_page = len(front) + 1
    solutions_start = len(pages) + 1
    if "solutions" in spec.back_matter:
        per = spec.solutions.per_page
        cols = 2 if per > 1 else 1
        rows = -(-per // cols)
        trim_s, mm = _geometry(spec, est_pages, edition)
        t = TRIMS[trim_s]
        cell_h = (
            t.height_in - mm["top"] - mm["bottom"] - TITLE_SPACE_IN
        ) / rows - SOLUTION_TITLE_IN
        sctx = _ctx(spec, est_pages, w_share=1 / cols * 0.94, h=cell_h, edition=edition)
        for k in range(0, len(puzzles), per):
            items = []
            for n, pz in enumerate(puzzles[k : k + per], k + 1):
                rb = get_puzzle_type(pz.type).render_solution(pz, sctx)
                built.files.update(rb.files)
                items.append(
                    {"title": f"#{n}  (page {built.puzzle_pages[pz.id]})", "blocks": rb.blocks}
                )
            pages.append(
                Page(
                    kind="solutions",
                    title="Solutions",
                    blocks=[{"kind": "cells", "columns": cols, "items": items}],
                )
            )
            for pz in puzzles[k : k + per]:
                built.solution_pages[pz.id] = len(pages)
    if "about" in spec.back_matter:
        pages.append(
            Page(
                kind="text", title="About This Book", blocks=[{"kind": "paragraph", "text": ABOUT}]
            )
        )
    if "thank_you" in spec.back_matter:
        pages.append(
            Page(kind="text", title="Thank You", blocks=[{"kind": "paragraph", "text": THANK_YOU}])
        )
    if toc_index is not None:
        entries = [
            {
                "title": "How to Play",
                "page": 1 + next((i for i, p in enumerate(pages) if p.title == "How to Play"), 0),
            }
        ]
        entries.append({"title": "Puzzles", "page": first_puzzle_page})
        if "solutions" in spec.back_matter:
            entries.append({"title": "Solutions", "page": solutions_start})
        pages[toc_index] = Page(
            kind="text", title="Contents", blocks=[{"kind": "toc", "entries": entries}]
        )
    trim, margins = _geometry(spec, est_pages, edition)
    built.doc = make_layout(
        title=b.title,
        subtitle=b.subtitle,
        author=b.author,
        trim=trim,
        pages=pages,
        large_print=b.large_print,
        margins=margins if edition and edition.name != "kdp" else None,
        edition=edition.layout_extra() if edition and edition.name != "kdp" else None,
    )
    return built


def manifest(spec: BookSpec, book_id: str, puzzles: list[Puzzle], built: Built) -> dict[str, Any]:
    requested = {s.index: s.requested_level for s in plan_book(spec) if s.requested_level}
    return {
        "book_id": book_id,
        "forge_version": __version__,
        "spec": spec.model_dump(mode="json"),
        "page_count": len(built.doc.pages),
        "trim": spec.book.trim,
        "puzzles": [
            {
                "n": n,
                "id": p.id,
                "type": p.type,
                "level": p.spec.level,
                "requested_level": requested.get(n - 1),
                "theme": p.spec.theme,
                "seed": p.seed,
                "content_hash": p.content_hash,
                "difficulty": p.difficulty.model_dump() if p.difficulty else None,
                "verify": p.verify.model_dump() if p.verify else None,
                "page": built.puzzle_pages[p.id],
                "solution_page": built.solution_pages.get(p.id),
            }
            for n, p in enumerate(puzzles, 1)
        ],
    }


FIX_OFFSETS = "qa/fix_offsets.json"


def load_offsets(out_dir: Path) -> dict[int, int]:
    p = out_dir / FIX_OFFSETS
    return {int(k): int(v) for k, v in json.loads(p.read_text()).items()} if p.is_file() else {}


def build_book(
    spec: BookSpec,
    out_root: Path,
    db_path: Path,
    render: bool = True,
    plan: ContentPlan | None = None,
) -> Path:
    book_id = book_id_for(spec)
    out = out_root / book_id
    out.mkdir(parents=True, exist_ok=True)
    if plan is None and (out / PLAN_FILE).is_file():
        plan = load_plan(out / PLAN_FILE)  # --from-stage puzzles: reuse the (edited) plan
    if plan is not None:
        problems = validate_plan(plan, plan_book(spec), spec.book.audience)
        if problems:
            raise BuildError("content plan invalid:\n  " + "\n  ".join(problems[:30]))
        save_plan(plan, out / PLAN_FILE)
        (out / ILLUSTRATIONS_FILE).write_text(
            json.dumps(illustration_requests(plan), indent=1), encoding="utf-8"
        )
    with Registry(db_path) as reg:
        reg.remove_book(book_id)  # rebuild = this book's puzzles are re-registered
        puzzles = generate_puzzles(spec, book_id, reg, load_offsets(out), plan)
    built = layout_book(spec, puzzles)
    built = layout_book(spec, puzzles, est_pages=len(built.doc.pages))  # gutter by real count
    (out / "puzzles.jsonl").write_text(
        "".join(p.model_dump_json() + "\n" for p in puzzles), encoding="utf-8"
    )
    (out / "manifest.json").write_text(
        json.dumps(manifest(spec, book_id, puzzles, built), indent=1), encoding="utf-8"
    )
    (out / "layout.json").write_text(built.doc.to_json(), encoding="utf-8")
    if render:
        from forge.layout.document import render_pdf

        render_pdf(built.doc, out / "interior.pdf", files=built.files)
    return out


def load_puzzles(out_dir: Path) -> list[Puzzle]:
    lines = (out_dir / "puzzles.jsonl").read_text(encoding="utf-8").splitlines()
    return [Puzzle.model_validate_json(x) for x in lines if x.strip()]


def verify_book(out_dir: Path) -> list[str]:
    """Re-verify every puzzle with its independent solver; returns problems (empty = OK)."""
    problems: list[str] = []
    man = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    puzzles = load_puzzles(out_dir)
    if len(puzzles) != len(man["puzzles"]):
        problems.append("manifest and puzzles.jsonl disagree on the puzzle count")
    for n, (pz, row) in enumerate(zip(puzzles, man["puzzles"], strict=False), 1):
        if pz.id != row["id"] or pz.content_hash != row["content_hash"]:
            problems.append(f"#{n}: manifest entry does not match puzzle data")
        rep = get_puzzle_type(pz.type).verify(pz)
        if not rep.ok:
            problems.append(f"#{n} {pz.id}: {'; '.join(rep.messages)}")
    if man["page_count"] % 2:
        problems.append("odd page count")
    if not (out_dir / "interior.pdf").is_file():
        problems.append("interior.pdf missing")
    return problems
