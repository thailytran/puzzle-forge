"""CBN Mystery: case frame -> checked case -> puzzle pages -> book (docs/MYSTERY_DESIGN.md §15-§16).

Pipeline (owner spec §6.4): an LLM writes the *case frame* as JSON (setting, suspects, final answer,
chapters). Python then
  1. checks the frame (`check_frame`): every clue is needed and together they leave exactly one
     suspect (`necessity.check_case`), every reveal code fits its mosaic, every side-puzzle keyword
     can be built by its generator, texts are family-safe;
  2. generates the puzzle pages from the locked answers (`build_puzzles`) and verifies each one;
  3. lays the book out (`layout_pages`): per chapter a story page, the colour-by-number page, two
     side puzzles and an evidence card; then deduction page, hints, solutions, Case Vault page.

Clues live only in code-generated parts (mosaic code, keywords, evidence table). Art is listed in
`art_requests` for the image tool and never carries information the reader needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from forge.core.models import Audience, Level, Puzzle, PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.layout.document import Page
from forge.mystery import necessity
from forge.puzzles.base import GenerationError
from forge.puzzles.cbn import ColorByNumber, plan_tiling
from forge.puzzles.cbn.font import GLYPHS, SYMBOLS
from forge.puzzles.cbn.tiling import SHAPES
from forge.wordlists import is_blocked

SIDE_TYPES = ("scramble", "cryptogram", "wordsearch", "maze")
MAX_ROUNDS = 3  # frame goes back to the writer at most this many times (owner spec §6.4)
UNSAFE = re.compile(
    r"\b(murder|murdered|kill|killed|killer|blood|bloody|corpse|dead body|gun|stab|poison|"
    r"strangle|suicide|kidnap)\w*\b",
    re.I,
)
CHAPTERS = {"adult": (6, 10), "kids": (3, 5)}  # allowed chapter counts
LEVELS: tuple[Level, ...] = ("easy", "easy", "medium", "medium", "medium", "hard", "hard", "hard")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Decoy(_M):
    """A wrong reading on the evidence card: only solving the mosaic tells which row is true."""

    symbol: str
    meaning: str


class SidePuzzle(_M):
    type: Literal["scramble", "cryptogram", "wordsearch", "maze"]
    keyword: str
    intro: str = ""


class Chapter(_M):
    no: int
    title: str
    story: str
    scene: str = ""  # picture brief for the image tool (illustration only)
    shape: str = "square"
    symbol: str  # code revealed by the colour-by-number page (1-2 glyphs or a symbol name)
    meaning: str  # what the symbol means (reader-facing sentence on the evidence card)
    clue: dict[str, Any]  # the same meaning as an exclusion rule over the suspects
    decoys: list[Decoy] = Field(default_factory=list)
    side: list[SidePuzzle] = Field(default_factory=list)
    evidence: str = ""
    hints: list[str] = Field(default_factory=list)  # three tiers: nudge, method, answer


class CaseFrame(_M):
    id: str
    title: str
    subtitle: str = ""
    audience: Audience = "adult"
    season: str = ""
    setting: str
    intro: str
    suspects: list[dict[str, Any]]
    answer: str
    answer_field: str = "name"
    chapters: list[Chapter]
    finale: str = ""
    epilogue: str = ""
    vault_word: str = ""


def code_of(symbol: str) -> str:
    """Glyph string the mosaic reveals for a chapter symbol ("star" -> "*", "r7" -> "R7")."""
    s = symbol.strip()
    return SYMBOLS.get(s.lower(), s.upper())


def _kids(aud: str) -> bool:
    return aud.startswith("kids")


def cbn_spec(frame: CaseFrame, ch: Chapter, idx: int) -> PuzzleSpec:
    level: Level = "easy" if _kids(frame.audience) else LEVELS[min(idx, len(LEVELS) - 1)]
    return PuzzleSpec.model_validate(
        {
            "type": "cbn",
            "level": level,
            "audience": frame.audience,
            "options": {"shape": ch.shape, "mode": "A"},
            "constraints": [{"kind": "answer_is", "word": code_of(ch.symbol)}],
        }
    )


def side_spec(frame: CaseFrame, sp: SidePuzzle, idx: int) -> PuzzleSpec:
    level: Level = "easy" if _kids(frame.audience) else LEVELS[min(idx, len(LEVELS) - 1)]
    kw = sp.keyword.upper()
    cons: dict[str, Any]
    if sp.type == "wordsearch":
        cons = {"kind": "hidden_message", "text": kw}
    elif sp.type == "maze":
        cons = {"kind": "path_letters", "seq": kw}
    else:
        cons = {"kind": "answer_is", "word": kw}
    data: dict[str, Any] = {
        "type": sp.type,
        "level": level,
        "audience": frame.audience,
        "constraints": [cons],
    }
    if sp.type in ("wordsearch", "scramble"):
        data["theme"] = "holidays" if frame.season else "weather"
    return PuzzleSpec.model_validate(data)


def _side_type(name: str) -> Any:
    if name == "scramble":
        from forge.puzzles.scramble import Scramble

        return Scramble()
    if name == "cryptogram":
        from forge.puzzles.cryptogram import Cryptogram

        return Cryptogram()
    if name == "wordsearch":
        from forge.puzzles.wordsearch import WordSearch

        return WordSearch()
    from forge.puzzles.maze import Maze

    return Maze()


def _generate(pt: Any, spec: PuzzleSpec, seed: int, tries: int = 6) -> Puzzle:
    """Generate + verify; a puzzle that fails verification is discarded and regenerated."""
    last = "no attempt"
    for k in range(tries):
        try:
            pz: Puzzle = pt.generate(spec, seed + 1009 * k)
        except (GenerationError, KeyError, ValueError) as e:
            last = str(e)
            continue
        if pt.verify(pz).ok:
            return pz
        last = "verification failed"
    raise GenerationError(f"{spec.type}: {last}")


@dataclass
class FrameReport:
    problems: list[str] = field(default_factory=list)
    necessity: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems

    def feedback(self) -> str:
        """Text sent back to the writer when the frame is rejected."""
        return "The case frame was rejected:\n" + "\n".join(f"- {p}" for p in self.problems)


def _texts(frame: CaseFrame) -> list[tuple[str, str]]:
    out = [("setting", frame.setting), ("intro", frame.intro), ("finale", frame.finale)]
    out.append(("epilogue", frame.epilogue))
    for ch in frame.chapters:
        out += [(f"chapter {ch.no} story", ch.story), (f"chapter {ch.no} meaning", ch.meaning)]
        out += [(f"chapter {ch.no} evidence", ch.evidence)]
        out += [(f"chapter {ch.no} hint", h) for h in ch.hints]
    return out


def check_frame(frame: CaseFrame, seed: int = 1, deep: bool = True) -> FrameReport:
    """All structural, logical and buildability problems of a case frame (empty = accepted).

    deep=True also builds every side puzzle once, so a keyword no generator can place is caught
    before any text or art is paid for."""
    rep = FrameReport()
    p = rep.problems
    names = [str(s.get(frame.answer_field, "")) for s in frame.suspects]
    if len(frame.suspects) < 4:
        p.append(f"need at least 4 suspects, got {len(frame.suspects)}")
    if len(set(names)) != len(names) or "" in names:
        p.append("every suspect needs a unique name")
    if frame.answer not in names:
        p.append(f"answer {frame.answer!r} is not one of the suspects")
    lo, hi = CHAPTERS["kids" if _kids(frame.audience) else "adult"]
    if not lo <= len(frame.chapters) <= hi:
        p.append(f"{frame.audience} books have {lo}-{hi} chapters, got {len(frame.chapters)}")
    if [c.no for c in frame.chapters] != list(range(1, len(frame.chapters) + 1)):
        p.append("chapters must be numbered 1..n in order")
    seen: dict[str, int] = {}
    keys: dict[str, int] = {}
    for i, ch in enumerate(frame.chapters):
        code = code_of(ch.symbol)
        tag = f"chapter {ch.no}"
        if not code or any(c not in GLYPHS for c in code) or len(code) > 2:
            p.append(f"{tag}: symbol {ch.symbol!r} must be 1-2 letters / digits or a known symbol")
            continue
        if code in seen:
            p.append(f"{tag}: symbol {code!r} already used in chapter {seen[code]}")
        seen[code] = ch.no
        if ch.shape not in SHAPES:
            p.append(f"{tag}: unknown cell shape {ch.shape!r} (use {', '.join(SHAPES)})")
        else:
            try:
                plan_tiling(ch.shape, code, cbn_spec(frame, ch, i))
            except GenerationError as e:
                p.append(f"{tag}: {e}")
        dec = [code_of(d.symbol) for d in ch.decoys]
        if len(ch.decoys) < 2:
            p.append(f"{tag}: the evidence card needs at least 2 decoy readings")
        if code in dec or len(set(dec)) != len(dec):
            p.append(f"{tag}: decoy symbols must differ from each other and from the real one")
        if len(ch.side) != 2:
            p.append(f"{tag}: needs exactly 2 side puzzles, got {len(ch.side)}")
        if len(ch.hints) != 3:
            p.append(f"{tag}: needs 3 hint tiers, got {len(ch.hints)}")
        for sp in ch.side:
            kw = sp.keyword.upper()
            if not re.fullmatch(r"[A-Z]{3,12}", kw):
                p.append(f"{tag}: keyword {sp.keyword!r} must be one word of 3-12 letters")
                continue
            if kw in keys:
                p.append(f"{tag}: keyword {kw} already used in chapter {keys[kw]}")
            keys[kw] = ch.no
            if is_blocked(kw.lower()):
                p.append(f"{tag}: keyword {kw} is on the blocklist")
            if deep:
                try:
                    _generate(_side_type(sp.type), side_spec(frame, sp, i), seed + 97 * ch.no, 3)
                except GenerationError as e:
                    p.append(f"{tag}: {sp.type} cannot produce keyword {kw} ({e})")
    for where, text in _texts(frame):
        m = UNSAFE.search(text or "")
        if m:
            p.append(f"{where}: not family-friendly ({m.group(0)!r})")
    if frame.vault_word:
        initials = "".join(sp.keyword[0].upper() for ch in frame.chapters for sp in ch.side)
        if frame.vault_word.upper() != initials:
            p.append(f"vault_word must spell the keyword initials {initials!r}")
    try:
        clues = [{**ch.clue, "id": f"ch{ch.no}", "text": ch.meaning} for ch in frame.chapters]
        nr = necessity.check_case(
            {
                "space": {"candidates": frame.suspects},
                "clues": clues,
                "answer": frame.answer,
                "answer_field": frame.answer_field,
            }
        )
        rep.necessity = {"solutions": nr.solutions, "redundant": nr.redundant, "ok": nr.ok}
        p.extend(nr.problems())
    except (necessity.CaseError, KeyError) as e:
        p.append(f"clue logic: {e}")
    return rep


@dataclass
class ChapterPuzzles:
    cbn: Puzzle
    side: list[Puzzle]


def build_puzzles(frame: CaseFrame, seed: int) -> list[ChapterPuzzles]:
    out = []
    cb = ColorByNumber()
    for i, ch in enumerate(frame.chapters):
        base = seed + 10007 * ch.no
        cbn = _generate(cb, cbn_spec(frame, ch, i), base)
        side = [
            _generate(_side_type(sp.type), side_spec(frame, sp, i), base + 31 * (k + 1))
            for k, sp in enumerate(ch.side)
        ]
        out.append(ChapterPuzzles(cbn, side))
    return out


# --- layout ---------------------------------------------------------------------------------


def _para(text: str) -> list[dict[str, Any]]:
    return [{"kind": "paragraph", "text": t.strip()} for t in text.split("\n") if t.strip()]


def _evidence_rows(ch: Chapter) -> list[str]:
    rows = [(code_of(ch.symbol), ch.meaning)] + [(code_of(d.symbol), d.meaning) for d in ch.decoys]
    rows.sort(key=lambda r: r[0])  # the true reading is not always first
    return [f"If the picture shows  {SYMBOL_NAMES.get(c, c)}  →  {m}" for c, m in rows]


SYMBOL_NAMES = {v: f"{v} ({k})" for k, v in SYMBOLS.items()}


def layout_pages(
    frame: CaseFrame, puzzles: list[ChapterPuzzles], ctx: RenderCtx
) -> tuple[list[Page], dict[str, bytes], list[dict[str, Any]]]:
    """Pages of the book, side files (maze SVGs ...) and the art requests (page, zone, brief)."""
    cb = ColorByNumber()
    pages: list[Page] = []
    files: dict[str, bytes] = {}
    art: list[dict[str, Any]] = []
    half = RenderCtx(width_in=ctx.width_in, height_in=ctx.height_in * 0.46)

    def add(page: Page, brief: str = "", zone: str = "scene") -> None:
        pages.append(page)
        if brief:
            art.append({"page": len(pages), "zone": zone, "brief": brief})

    add(
        Page(kind="title", title=frame.title, header=False, number=False, blocks=[]),
        f"Cover art for '{frame.title}': {frame.setting}",
        "cover_art",
    )
    add(
        Page(
            kind="text",
            title="How To Play",
            blocks=[
                *_para(frame.intro),
                {
                    "kind": "list",
                    "items": [
                        "Read the chapter story.",
                        "Colour the mosaic by number. A hidden symbol appears.",
                        "Solve the two side puzzles. Each gives one keyword.",
                        "Open the evidence card and read the line for YOUR symbol only.",
                        "Write the symbol and both keywords in the Code Log.",
                        "After the last chapter, cross out suspects until one is left.",
                    ],
                },
                {
                    "kind": "paragraph",
                    "text": "Stuck? Three hints per chapter wait near the end of the book.",
                },
            ],
        )
    )
    who = [
        ", ".join(
            [str(s[frame.answer_field])]
            + [f"{k}: {_show(v)}" for k, v in s.items() if k != frame.answer_field]
        )
        for s in frame.suspects
    ]
    add(
        Page(
            kind="text",
            title="The Suspects",
            blocks=[*_para(frame.setting), {"kind": "list", "items": who}],
        ),
        "Portrait strip of the suspects, friendly storybook style",
        "portraits",
    )
    log = [
        f"Chapter {ch.no}:   symbol ______   keywords ______________  ______________"
        for ch in frame.chapters
    ]
    add(Page(kind="text", title="Code Log", blocks=[{"kind": "list", "items": log}]))
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        add(
            Page(kind="text", title=f"Chapter {ch.no}: {ch.title}", blocks=_para(ch.story)),
            ch.scene,
        )
        front = cb.render(cp.cbn, ctx)
        files.update(front.files)
        add(Page(kind="puzzle", title=f"Chapter {ch.no}: The Hidden Symbol", blocks=front.blocks))
        for k, (sp, pz) in enumerate(zip(ch.side, cp.side, strict=True), 1):
            r = _side_type(sp.type).render(pz, ctx)
            files.update(r.files)
            intro = _para(sp.intro) if sp.intro else []
            tail = {"kind": "paragraph", "text": f"Keyword {k}: ____________________"}
            add(
                Page(
                    kind="puzzle",
                    title=f"Chapter {ch.no}: Keyword {k}",
                    blocks=[*intro, *r.blocks, tail],
                )
            )
        add(
            Page(
                kind="text",
                title=f"Evidence Card {ch.no}",
                blocks=[
                    *_para(ch.evidence),
                    {"kind": "list", "items": _evidence_rows(ch)},
                    {
                        "kind": "paragraph",
                        "text": "Only the line that matches your symbol is true. "
                        "Note it in the Code Log.",
                    },
                ],
            )
        )
    add(
        Page(
            kind="text",
            title="The Final Deduction",
            blocks=[
                *_para(frame.finale),
                {
                    "kind": "list",
                    "items": [f"[   ]  {s[frame.answer_field]}" for s in frame.suspects],
                },
                {"kind": "paragraph", "text": "It was: ______________________________"},
            ],
        )
    )
    for lo in range(0, len(frame.chapters), 4):
        blocks: list[dict[str, Any]] = []
        for ch in frame.chapters[lo : lo + 4]:
            blocks.append({"kind": "heading", "text": f"Chapter {ch.no}", "level": 2})
            blocks.append(
                {"kind": "list", "items": [f"Hint {i}: {h}" for i, h in enumerate(ch.hints, 1)]}
            )
        add(Page(kind="text", title="Hints", blocks=blocks))
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        back = cb.render_solution(cp.cbn, half)
        files.update(back.files)
        blocks = [{"kind": "heading", "text": f"Chapter {ch.no}", "level": 2}, *back.blocks]
        keys = ", ".join(sp.keyword.upper() for sp in ch.side)
        blocks.append(
            {"kind": "paragraph", "text": f"Keywords: {keys}. True reading: {ch.meaning}"}
        )
        add(Page(kind="solutions", title="Solutions", blocks=blocks))
    add(
        Page(
            kind="text",
            title="Case Closed?",
            blocks=[
                *_para(frame.epilogue),
                {
                    "kind": "paragraph",
                    "text": "Check your answer in the Case Vault with the Book Code "
                    "on this page and unlock the reward for the next case.",
                },
            ],
        )
    )
    return pages, files, art


def _show(v: Any) -> str:
    return "yes" if v is True else "no" if v is False else str(v)


def manifest(frame: CaseFrame, puzzles: list[ChapterPuzzles], rep: FrameReport) -> dict[str, Any]:
    rows = []
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        for role, pz in [("cbn", cp.cbn)] + [(f"side{k}", s) for k, s in enumerate(cp.side, 1)]:
            rows.append(
                {
                    "chapter": ch.no,
                    "role": role,
                    "id": pz.id,
                    "type": pz.type,
                    "content_hash": pz.content_hash,
                    "shape": pz.data.get("shape") if pz.type == "cbn" else None,
                    "verified": True,
                }
            )
    return {
        "case": frame.id,
        "title": frame.title,
        "audience": frame.audience,
        "answer_field": frame.answer_field,
        "chapters": len(frame.chapters),
        "puzzle_pages": len(rows),
        "frame_check": {  # the answer itself stays out of the manifest
            "ok": rep.ok,
            "unique": len(rep.necessity.get("solutions", [])) == 1,
            "redundant": rep.necessity.get("redundant", []),
        },
        "puzzles": rows,
    }


def load_frame(path: Any) -> CaseFrame:
    import json
    from pathlib import Path

    return CaseFrame.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def build_case_book(
    frame: CaseFrame, out_dir: Any, seed: int = 20261118, trim: str = "8.5x11", render: bool = True
) -> dict[str, Any]:
    """Check the frame, generate + verify every puzzle, lay out and render the book.

    Writes interior.pdf (when a Typst backend exists), manifest.json and art_requests.json."""
    import json
    from pathlib import Path

    from forge.layout.document import make_layout, render_pdf
    from forge.layout.trim import TRIMS, margins_for

    rep = check_frame(frame, seed)
    if not rep.ok:
        raise necessity.CaseError(rep.feedback())
    puzzles = build_puzzles(frame, seed)
    t = TRIMS[trim]
    m = margins_for(72)
    ctx = RenderCtx(
        width_in=t.width_in - m.inside - m.outside,
        height_in=t.height_in - m.top - m.bottom - 0.9,
    )
    pages, files, art = layout_pages(frame, puzzles, ctx)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    man = manifest(frame, puzzles, rep)
    man.update({"seed": seed, "trim": trim, "pages": len(pages)})
    (out / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    (out / "art_requests.json").write_text(json.dumps(art, indent=2), encoding="utf-8")
    if render:
        doc = make_layout(
            title=frame.title, subtitle=frame.subtitle, trim=trim, pages=pages, min_pages=0
        )
        render_pdf(doc, out / "interior.pdf", files=files)
    return man
