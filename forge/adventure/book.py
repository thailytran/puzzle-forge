"""Adventure book: verified frame + Studio art -> pages -> interior.pdf (ROADMAP P9.2-P9.5).

Page order (US Letter, page 1 = right-hand page):
  front   title · inspired-by/credits · how to play · the cast · Lock Log · prologue spread
  chapter (6 pages, the story always on a LEFT page so the search scene faces it)
          story (L) | search (R) | Puzzle A (L) | Puzzle B (R) | key page (L) | field notes (R)
  back    final challenge · epilogue · answer key: hidden objects · solutions · Case Vault page

Studio contract (docs/adventures/STUDIO_ADVENTURE.md): `art_dir` holds `<key>.png` pictures,
`selfcheck.json` (Gemini: where it drew each object) and `review.json` (owner ticks). The
hidden-object answer key prints only objects that Gemini marked AND the owner ticked; the build
reports every chapter that is still pending (`manifest["search_check"]`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge.adventure import pages as pg
from forge.adventure.frame import (
    LABELS,
    AdventureFrame,
    ChapterPuzzles,
    build_puzzles,
    check_frame,
    code_type,
    puzzle_type,
    simulate_reader,
)
from forge.adventure.objects import icon_sheet_brief, norm
from forge.core.protocol import RenderCtx
from forge.layout.document import Page
from forge.mystery.necessity import CaseError

STORY_STYLE = "adv_story"
FULL_STYLE = "fullpage"


def paragraphs(text: str, per: int = 2) -> list[str]:
    """Owner look: 5-6 short paragraphs. Keep given breaks; else group every `per` sentences."""
    parts = [t.strip() for t in text.split("\n") if t.strip()]
    if len(parts) > 1:
        return parts
    sents = re.split(
        r"(?:(?<=[.!?\u2026])|(?<=[.!?\u2026][\"\u201d\u2019]))\s+(?=[\"\u201cA-Z])", text.strip()
    )
    out: list[str] = []
    cur: list[str] = []
    for s in sents:
        cur.append(s)
        joined = " ".join(cur)
        open_quote = (joined.count('"') % 2 == 1) or joined.count("“") > joined.count("”")
        if len(cur) >= per and not open_quote:
            out.append(joined)
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def _para(text: str) -> list[dict[str, Any]]:
    return [{"kind": "paragraph", "text": t} for t in paragraphs(text)]


class _Book:
    """Collects pages, side files and art requests while keeping track of left/right pages."""

    def __init__(self, frame: AdventureFrame, art: dict[str, Path], size: tuple[float, float]):
        self.frame = frame
        self.art = art
        self.size = size
        self.pages: list[Page] = []
        self.files: dict[str, bytes] = {}
        self.requests: list[dict[str, Any]] = []
        self.used: set[str] = set()
        self.missing: list[str] = []
        self.chapter_pages = 0  # story .. field notes of every chapter (QA: >= 48)

    @property
    def next_is_left(self) -> bool:
        return (len(self.pages) + 1) % 2 == 0

    def pic(self, key: str) -> Path | None:
        p = self.art.get(key)
        if p is None:
            if key not in self.missing:
                self.missing.append(key)
        else:
            self.used.add(key)
        return p

    def request(self, key: str, zone: str, brief: str, aspect: str, **extra: Any) -> None:
        req: dict[str, Any] = {
            "id": key,
            "zone": zone,
            "page": len(self.pages) + 1,
            "aspect": aspect,
            "brief": brief,
            "style": self.frame.art_style,
        }
        who = [c for c in self.frame.cast if c.name.split(" (")[0].split()[0] in brief]
        if who:
            req["refs"] = [f"char:{c.id}" for c in who]
            req["characters"] = [{"id": c.id, "name": c.name, "look": c.look} for c in who]
        req.update(extra)
        self.requests.append(req)

    def add(self, page: Page) -> None:
        self.pages.append(page)

    def full(self, name: str, data: bytes, title: str) -> None:
        self.files[name] = data
        self.add(
            Page(kind="puzzle", title=title, header=False, style={"type": FULL_STYLE, "bg": name})
        )

    def story(self, key: str, heading: str, text: str, brief: str) -> None:
        if not self.next_is_left:
            self.filler()
        self.request(key, "vignette", brief, "5:4")
        name = f"adv/{key.replace(':', '_')}_page.png"
        self.files[name] = pg.story_page(
            heading, self.pic(key), *self.size, border=self.art.get("design:border"), label=key
        )
        x, y, w, h = pg.STORY_BOX
        self.add(
            Page(
                kind="text",
                title=heading,
                header=False,
                blocks=_para(text),
                style={"type": STORY_STYLE, "bg": name, "box": {"x": x, "y": y, "w": w, "h": h}},
            )
        )

    def filler(self) -> None:
        """Keeps every story on a left page: the library map (colouring) first, then notes."""
        if not any(p.title == "The Library Map" for p in self.pages):
            self.request("map", "map", f"Bird's-eye line-art map of {self.frame.setting}", "3:4")
            name = "adv/map_page.png"
            im = pg.blank(*self.size)
            x0, y0, x1, y1 = pg.draw_frame(im, self.art.get("design:border"))
            im.paste(pg.line_art(self.pic("map"), (x1 - x0, y1 - y0), "map"), (x0, y0))
            self.full(name, pg.png(im), "The Library Map")
        else:
            self.add(Page(kind="notes", title="Field Notes"))


ART_PREFIXES = ("search", "icons", "vignette", "design", "char", "loc", "find", "col")
STUDIO_ALIASES = (("find:", "search:"),)  # HALOSPARK Studio keys (mystery_art.adv_requests)


def art_keys(found: dict[str, Path]) -> dict[str, Path]:
    """Studio art keys -> Forge keys. File names cannot hold ':' on Windows (``search_ch1.png`` is
    ``search:ch1``); Studio names the search scene ``find:chN`` and the story vignette ``chN``."""
    out = dict(found)
    for k, v in found.items():
        head, sep, tail = k.partition("_")
        if sep and head in ART_PREFIXES:
            out.setdefault(f"{head}:{tail}", v)
    for k, v in list(out.items()):
        for a, b in STUDIO_ALIASES:
            if k.startswith(a):
                out.setdefault(b + k[len(a) :], v)
        if re.fullmatch(r"ch\d+", k):
            out.setdefault(f"vignette:{k}", v)
    return out


def _how_to_play(frame: AdventureFrame) -> list[dict[str, Any]]:
    n = len(frame.chapters)
    return [
        {
            "kind": "list",
            "numbered": True,
            "items": [
                "READ the story of each room on the left-hand page.",
                "SEARCH the scene on the right-hand page. Tick every object in the column "
                "when you find it, then colour the whole page.",
                "SOLVE Puzzle A. The first letter of its answer is the room's KEY LETTER.",
                "SOLVE Puzzle B. Its number is the SLOT where that letter belongs.",
                f"WRITE the letter into its slot in the Lock Log. After all {n} rooms, read the "
                "slots in order: the word opens the final door.",
                "COLOUR as you go. Answers and every hidden object are at the back of the book.",
            ],
        },
        {"kind": "spacer", "height_in": 0.2},
        {"kind": "heading", "text": "The final challenge", "level": 2},
        {
            "kind": "paragraph",
            "text": f"{n} rooms, {n} keys, one word. You need every key: a single missing "
            "letter leaves the lock shut.",
        },
    ]


def _puzzle_page(
    ch_no: int, part: str, t: str, pz: Any, intro: str, ctx: RenderCtx, tail: str
) -> tuple[Page, dict[str, bytes]]:
    r = puzzle_type(t).render(pz, ctx)
    blocks = [*(_para(intro) if intro else []), *r.blocks]
    blocks.append({"kind": "spacer", "height_in": 0.15})
    blocks.append({"kind": "paragraph", "text": tail})
    title = f"Chapter {ch_no} · Puzzle {part}: {LABELS[t]}"
    return Page(kind="puzzle", title=title, blocks=blocks), dict(r.files)


def _marks(art_dir: Path | None, no: int, names: list[str]) -> tuple[list[dict[str, Any]], dict]:
    """Gemini self-check marks the owner ticked, plus the check status of this chapter."""
    sc: dict[str, Any] = {}
    rv: dict[str, Any] = {}
    if art_dir is not None:
        f = Path(art_dir) / "selfcheck.json"
        if f.is_file():
            sc = json.loads(f.read_text(encoding="utf-8"))
        f = Path(art_dir) / "review.json"
        if f.is_file():
            rv = json.loads(f.read_text(encoding="utf-8"))
    key = f"ch{no}"
    raw = {norm(str(m.get("name", ""))): m for m in sc.get(key, [])}
    ticks = {norm(k): bool(v) for k, v in (rv.get(key) or {}).items()}
    marks = [{**raw[n], "name": n} for n in map(norm, names) if n in raw and ticks.get(n)]
    status = {
        "objects": len(names),
        "marked": sum(1 for n in map(norm, names) if n in raw),
        "ticked": len(marks),
        "unmarked": [n for n in map(norm, names) if n not in raw],
        "not_ticked": [n for n in map(norm, names) if n in raw and not ticks.get(n)],
    }
    status["ok"] = status["ticked"] == len(names)
    return marks, status


def layout_book(
    frame: AdventureFrame,
    puzzles: list[ChapterPuzzles],
    art: dict[str, Path],
    art_dir: Path | None = None,
    size: tuple[float, float] = (8.5, 11.0),
    text_in: tuple[float, float] = (7.0, 9.2),
) -> tuple[_Book, dict[str, Any]]:
    bk = _Book(frame, art, size)
    n = len(frame.chapters)
    for c in frame.cast:  # reference sheets first: every later picture is drawn from them
        bk.request(
            f"char:{c.id}",
            "character_sheet",
            f"Character sheet of {c.name} ({c.role}): front, side, face close-up. "
            f"Look (never changes): {c.look}",
            "3:2",
        )
    bk.request(
        "cover",
        "cover_art",
        f"Vivid luminous painted cover for '{frame.title}': {frame.setting} "
        "Ornate title area; three round badges PUZZLES / SEARCH / COLORING; a round "
        "'story edition' seal. No other text.",
        "3:4",
    )
    credit = frame.inspired_by.get("intro_line", "")
    bk.add(
        Page(
            kind="title",
            title=frame.title,
            header=False,
            number=False,
            blocks=[{"kind": "paragraph", "text": frame.inspired_by.get("cover_line", "")}]
            if frame.inspired_by.get("cover_line")
            else [],
        )
    )
    bk.add(
        Page(
            kind="text",
            title="About This Book",
            blocks=[
                *_para(credit),
                {
                    "kind": "paragraph",
                    "text": "Colour every page with pencils, gel pens or "
                    "fine markers. Place a sheet of card behind the page when you use markers.",
                },
            ],
        )
    )
    bk.add(Page(kind="text", title="How To Play", blocks=_how_to_play(frame)))
    cast = [f"{c.name}: {c.role}. {c.look[:1].upper()}{c.look[1:]}." for c in frame.cast]
    bk.add(
        Page(
            kind="text",
            title="The Cast",
            blocks=[*_para(frame.setting), {"kind": "list", "items": cast}],
        )
    )
    bk.files["adv/lock_empty.png"] = pg.lock_diagram(n)
    log_rows = [f"Room {ch.no} · {ch.room}:   letter ____   slot ____" for ch in frame.chapters]
    bk.add(
        Page(
            kind="text",
            title="The Lock Log",
            blocks=[
                {
                    "kind": "paragraph",
                    "text": "Write each key here as you find it, then copy the "
                    "letter into its slot of the lock.",
                },
                {"kind": "list", "items": log_rows},
                {"kind": "spacer", "height_in": 0.3},
                {"kind": "image", "path": "adv/lock_empty.png", "width_in": 5.6},
            ],
        )
    )
    if frame.prologue:
        bk.story(
            "prologue",
            f"Prologue | {frame.prologue_title}",
            frame.prologue,
            f"Line-art vignette of the prologue: {frame.prologue}",
        )
    w_txt, h_txt = text_in
    ctx = RenderCtx(width_in=w_txt, height_in=h_txt - 1.6)
    search: dict[str, Any] = {}
    first = 0
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        if not first:
            first = len(bk.pages) + (1 if bk.next_is_left else 2)
        bk.story(
            f"vignette:ch{ch.no}",
            f"Chapter {ch.no} | {ch.title}",
            ch.story,
            ch.vignette or f"Line-art vignette for chapter {ch.no}: {ch.story}",
        )
        names = [norm(o) for o in ch.hidden_objects]
        bk.request(
            f"search:ch{ch.no}",
            "search_scene",
            (ch.scene or f"{ch.room}, full of detail, from the chapter story: {ch.story}")
            + " Hide every object of this list exactly once, clearly drawn, large enough "
            "to find, not in the right-hand fifth of the picture: "
            + ", ".join(names)
            + ". After drawing, return a JSON list of the objects you drew with their "
            "centre x, y and radius r as fractions of the picture.",
            "3:4",
            objects=names,
            selfcheck=f"selfcheck.json:ch{ch.no}",
        )
        bk.request(f"icons:ch{ch.no}", "icon_sheet", icon_sheet_brief(names), "4:3", objects=names)
        icons = None
        sheet = bk.pic(f"icons:ch{ch.no}")
        if sheet is not None:
            icons = [x or None for x in pg.split_icon_sheet(sheet, len(names))]
        bk.full(
            f"adv/search_ch{ch.no}.png",
            pg.search_page(
                ch.no,
                names,
                bk.pic(f"search:ch{ch.no}"),
                icons,
                *size,
                border=art.get("design:border"),
            ),
            f"Chapter {ch.no} · Search",
        )
        ta, tb = code_type(ch.puzzle_a.type, "a"), code_type(ch.puzzle_b.type, "b")
        page, f = _puzzle_page(
            ch.no,
            "A",
            ta,
            cp.a,
            ch.puzzle_a.intro,
            ctx,
            "Answer: ______________________   Key letter: ____",
        )
        bk.files.update(f)
        bk.add(page)
        page, f = _puzzle_page(ch.no, "B", tb, cp.b, ch.puzzle_b.intro, ctx, "Slot number: ____")
        bk.files.update(f)
        bk.add(page)
        bk.add(
            Page(
                kind="text",
                title=f"Key {ch.no} of {n}",
                blocks=[
                    {"kind": "paragraph", "text": f"You have found the key of the {ch.room}."},
                    {
                        "kind": "list",
                        "items": [
                            "Key letter (first letter of Puzzle A): ________",
                            "Slot (answer of Puzzle B): ________",
                        ],
                    },
                    {
                        "kind": "paragraph",
                        "text": "Write them in the Lock Log, then mark the slot on the lock below.",
                    },
                    {"kind": "image", "path": "adv/lock_empty.png", "width_in": 5.0},
                    *(
                        [{"kind": "spacer", "height_in": 0.3}, *_para(ch.teaser)]
                        if ch.teaser
                        else []
                    ),
                ],
            )
        )
        bk.add(Page(kind="notes", title="Field Notes"))
        search[f"ch{ch.no}"] = _marks(art_dir, ch.no, names)
    bk.chapter_pages = len(bk.pages) - first + 1
    bk.add(
        Page(
            kind="text",
            title="The Final Challenge",
            blocks=[
                *_para(frame.final.intro or "Write every key letter into its slot."),
                {"kind": "image", "path": "adv/lock_empty.png", "width_in": 6.0},
                {"kind": "spacer", "height_in": 0.3},
                {
                    "kind": "paragraph",
                    "text": "The word that opens the door: ______________________",
                },
            ],
        )
    )
    if frame.epilogue:
        bk.story(
            "epilogue",
            f"Epilogue | {frame.epilogue_title}",
            frame.epilogue,
            f"Line-art vignette of the epilogue: {frame.epilogue}",
        )
    for lo in range(0, n, 2):  # hidden-object answer key: two chapters per page
        blocks: list[dict[str, Any]] = []
        for ch in frame.chapters[lo : lo + 2]:
            marks, _st = search[f"ch{ch.no}"]
            names = [norm(o) for o in ch.hidden_objects]
            name = f"adv/answers_ch{ch.no}.png"
            bk.files[name] = pg.answer_key(
                ch.no, names, art.get(f"search:ch{ch.no}"), marks, (w_txt * 0.62, h_txt * 0.40)
            )
            blocks += [
                {"kind": "heading", "text": f"Chapter {ch.no} · {ch.room}", "level": 2},
                {"kind": "image", "path": name, "width_in": round(w_txt * 0.62, 2)},
                {
                    "kind": "paragraph",
                    "font_pt": 8.5,
                    "text": "  ".join(f"{i}. {x}" for i, x in enumerate(names, 1)),
                },
            ]
        bk.add(Page(kind="solutions", title="Answers: Hidden Objects", blocks=blocks))
    half = RenderCtx(width_in=w_txt * 0.48, height_in=h_txt * 0.36)
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        ta, tb = code_type(ch.puzzle_a.type, "a"), code_type(ch.puzzle_b.type, "b")
        ra = puzzle_type(ta).render_solution(cp.a, half)
        rb = puzzle_type(tb).render_solution(cp.b, half)
        bk.files.update(ra.files)
        bk.files.update(rb.files)
        ans = ch.puzzle_a.answer.upper()
        bk.add(
            Page(
                kind="solutions",
                title="Solutions",
                blocks=[
                    {"kind": "heading", "text": f"Chapter {ch.no} · {ch.room}", "level": 2},
                    {
                        "kind": "cells",
                        "columns": 2,
                        "items": [
                            {"title": f"Puzzle A · {LABELS[ta]}", "blocks": ra.blocks},
                            {"title": f"Puzzle B · {LABELS[tb]}", "blocks": rb.blocks},
                        ],
                    },
                    *_para(" ".join(x for x in (ch.puzzle_a.explain, ch.puzzle_b.explain) if x)),
                    {
                        "kind": "paragraph",
                        "text": f"Answer {ans} → key letter {ans[0]}. Slot {ch.puzzle_b.digit}.",
                    },
                ],
            )
        )
    word = frame.final.word.upper()
    bk.files["adv/lock_full.png"] = pg.lock_diagram(n, {i + 1: c for i, c in enumerate(word)})
    bk.add(
        Page(
            kind="solutions",
            title="Solution: The Final Door",
            blocks=[
                {"kind": "paragraph", "text": "Don't open before you finish."},
                {
                    "kind": "list",
                    "items": [
                        f"Slot {ch.key.slot}: {ch.key.letter.upper()} (Chapter {ch.no})"
                        for ch in sorted(frame.chapters, key=lambda c: c.key.slot)
                    ],
                },
                {"kind": "image", "path": "adv/lock_full.png", "width_in": 6.0},
                {
                    "kind": "paragraph",
                    "text": f"The final word is {word}. Type it at "
                    "casevault.colorilax.com to unlock your reward.",
                },
            ],
        )
    )
    return bk, search


def spread_ok(pages: list[Page]) -> list[str]:
    """Every story page is a left page and is followed by its search page (or the next page)."""
    bad = []
    for i, p in enumerate(pages, 1):
        if (p.style or {}).get("type") == STORY_STYLE and i % 2 == 1:
            bad.append(f"page {i} ({p.title}) is a story page on the right")
    return bad


def build_adventure_book(
    frame: AdventureFrame,
    out_dir: Any,
    seed: int = 20261120,
    trim: str = "8.5x11",
    render: bool = True,
    art_dir: Any = None,
    vault_domain: str = "",
) -> dict[str, Any]:
    """Check the frame, build + verify the puzzles, play the book, lay it out and render it.

    Writes interior.pdf (when a Typst backend exists), manifest.json, art_requests.json and the
    composed page pictures under build/adv/."""
    from forge.layout.document import make_layout, render_pdf
    from forge.layout.trim import TRIMS, margins_for

    rep = check_frame(frame, seed, deep=False)
    if not rep.ok:
        raise CaseError(rep.feedback())
    puzzles = build_puzzles(frame, seed)
    run = simulate_reader(frame, puzzles)
    if not run.ok:
        raise CaseError("reader simulation failed: " + "; ".join(run.problems))
    t = TRIMS[trim]
    m = margins_for(72)
    art: dict[str, Path] = {}
    if art_dir is not None:
        from forge.mystery.art import load_art

        art = art_keys(load_art(Path(art_dir)))
    text_in = (t.width_in - m.inside - m.outside, t.height_in - m.top - m.bottom - 0.9)
    bk, search = layout_book(
        frame,
        puzzles,
        art,
        Path(art_dir) if art_dir else None,
        (t.width_in, t.height_in),
        text_in,
    )
    if vault_domain:
        from forge.vault.page import case_vault_page

        page, files = case_vault_page(frame.id, vault_domain)
        bk.add(page)
        bk.files.update(files)
    problems = spread_ok(bk.pages)
    if problems:
        raise CaseError("; ".join(problems))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    man: dict[str, Any] = {
        "book": frame.id,
        "line": frame.line,
        "title": frame.title,
        "audience": frame.audience,
        "seed": seed,
        "trim": trim,
        "chapters": len(frame.chapters),
        "pages": len(bk.pages),
        "content_pages": bk.chapter_pages,
        "frame_check": {"ok": rep.ok, "warnings": rep.warnings, "lock": rep.lock},
        "reader_sim": {"ok": run.ok, "word_length": len(run.word)},
        "puzzles": [
            {
                "chapter": ch.no,
                "part": part,
                "type": pz.type,
                "id": pz.id,
                "content_hash": pz.content_hash,
                "verified": True,
            }
            for ch, cp in zip(frame.chapters, puzzles, strict=True)
            for part, pz in (("A", cp.a), ("B", cp.b))
        ],
        "search_check": {k: st for k, (_m, st) in search.items()},
        "art": {"used": sorted(bk.used), "missing": bk.missing},
    }
    man["ready_for_review"] = not bk.missing and all(st["ok"] for _m, st in search.values())
    (out / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    (out / "art_requests.json").write_text(json.dumps(bk.requests, indent=2), encoding="utf-8")
    if render:
        doc = make_layout(
            title=frame.title, subtitle=frame.subtitle, trim=trim, pages=bk.pages, min_pages=0
        )
        render_pdf(doc, out / "interior.pdf", files=bk.files)
    else:  # no Typst: keep the composed pictures for a look
        for name, data in bk.files.items():
            if name.startswith("adv/"):
                f = out / "pages" / name.removeprefix("adv/")
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(data)
    return man
