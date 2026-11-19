"""CBN Mystery: case frame -> checked case -> puzzle pages -> book (docs/MYSTERY_DESIGN.md §15-§16).

How a chapter gives its clue (v2, owner review 2026-11-18):
  * the colour-by-number mosaic reveals a PICTURE of the evidence object (scarf, boot, ladder ...);
  * the two side puzzles each give one keyword = a TRAIT of that object (WOOLLEN, CRIMSON ...);
  * the evidence card has one row per (object, trait, trait); only the row the reader's three
     answers point at is true. Each other row differs in exactly the part one puzzle decides, so
     all three puzzles are needed, and every wrong row is a dead end.

Pipeline (owner spec §6.4): an LLM writes the *case frame* as JSON. Python then
  1. checks the frame (`check_frame`): structure, buildability, family-safe text, and the LOGIC
     LOCK - two independent solvers (`necessity`, `logic_lock`), small-hint rule, dead-end decoys,
     card keys, no answer leaked in the story, causal graph (`causal_graph`);
  2. generates the puzzle pages from the locked answers (`build_puzzles`) and verifies each one;
  3. plays the book as a reader (`simulate_reader`): solve in page order, look the card up with
     the solved answers only, cross suspects out - one suspect must remain only at the very end;
  4. lays the book out (`layout_pages`).

Clues live only in code-generated parts (mosaic picture, keywords, evidence table). Art is listed
in `art_requests` for the image tool and never carries information the reader needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from forge.core.models import Audience, Level, Puzzle, PuzzleSpec
from forge.core.protocol import RenderCtx
from forge.layout.document import Page
from forge.mystery import logic_lock, necessity
from forge.mystery.causal_graph import CausalGraph
from forge.puzzles.base import GenerationError
from forge.puzzles.cbn import ColorByNumber, plan_tiling, tiling, tiling_of
from forge.puzzles.cbn.font import ICONS
from forge.puzzles.cbn.tiling import SHAPES
from forge.wordlists import is_blocked

# Owner rule 2026-11-19: every puzzle must lead straight to the code, no filler. Word scramble and
# word search were dropped from this line (their word lists had nothing to do with the case).
SIDE_TYPES = ("shift", "maze", "numlock", "sudoku")
NUMBER_TYPES = ("numlock", "sudoku")  # their keyword is a number (shoe size, hour, house number)
SUDOKU_CELLS = [(0, 0), (1, 3), (2, 6), (3, 1)]  # different row, column and box: any digits fit
SUDOKU_CELLS_6 = [(0, 0), (1, 3), (2, 1), (3, 4)]
MIN_SUSPECTS, MAX_SUSPECTS = 9, 12  # owner decision 2026-11-19
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
    """A wrong row of the evidence card. It differs from the true row in the object or in one
    keyword; `clue` is what a reader who believed it would cross out (None = nothing)."""

    object: str
    keywords: list[str]
    meaning: str
    clue: dict[str, Any] | None = None


class SidePuzzle(_M):
    type: Literal["shift", "maze", "numlock", "sudoku"]
    keyword: str  # a trait of the chapter's evidence object (a word, or digits for number games)
    intro: str = ""
    message: str = ""  # shift cipher: the witness statement to decode (holds the keyword)


class Chapter(_M):
    no: int
    title: str
    story: str
    scene: str = ""  # picture brief for the image tool (illustration only)
    shape: str = "square"
    object: str  # evidence object whose picture the colour-by-number page reveals (icon name)
    meaning: str  # what object + both traits prove (reader-facing sentence on the evidence card)
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


def code_of(ch: Chapter) -> str:
    """Mosaic code of a chapter: the icon of its evidence object."""
    return "@" + ch.object.strip().lower()


Key = tuple[str, frozenset[str]]


def _key(obj: str, kws: list[str]) -> Key:
    return obj.strip().lower(), frozenset(k.strip().upper() for k in kws)


def card_rows(ch: Chapter) -> list[tuple[Key, str, dict[str, Any] | None, bool]]:
    """(key, meaning, rule, is_true) for every row of the evidence card, in printed order."""
    rows: list[tuple[Key, str, dict[str, Any] | None, bool]] = [
        (_key(ch.object, [sp.keyword for sp in ch.side]), ch.meaning, ch.clue, True)
    ]
    rows += [(_key(d.object, d.keywords), d.meaning, d.clue, False) for d in ch.decoys]
    rows.sort(key=lambda r: (sorted(r[0][1]), r[0][0]))  # the true row is not always first
    return rows


def _row_label(key: Key) -> str:
    return " + ".join([key[0].upper(), *sorted(key[1])])


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
            "constraints": [{"kind": "answer_is", "word": code_of(ch)}],
        }
    )


def keyword_ok(sp_type: str, kw: str, kids: bool = False) -> bool:
    if sp_type == "numlock":
        return bool(re.fullmatch(r"[0-9]{2,4}", kw))
    if sp_type == "sudoku":
        return bool(re.fullmatch(r"[1-6]{2,4}" if kids else r"[1-9]{2,4}", kw))
    return bool(re.fullmatch(r"[A-Z]{3,12}", kw))


def side_spec(frame: CaseFrame, sp: SidePuzzle, idx: int) -> PuzzleSpec:
    kids = _kids(frame.audience)
    level: Level = "easy" if kids else LEVELS[min(idx, len(LEVELS) - 1)]
    kw = sp.keyword.upper()
    cons: dict[str, Any]
    data: dict[str, Any] = {"type": sp.type, "level": level, "audience": frame.audience}
    if sp.type == "maze":
        cons = {"kind": "path_letters", "seq": kw}
    elif sp.type == "sudoku":
        cells = (SUDOKU_CELLS_6 if kids else SUDOKU_CELLS)[: len(kw)]
        cons = {"kind": "shaded_cells", "cells": cells, "expect": kw}
        data["options"] = {"size": 6 if kids else 9}
        data["level"] = "easy" if level == "easy" else "medium"
    else:
        cons = {"kind": "answer_is", "word": kw}
    data["constraints"] = [cons]
    if sp.type == "shift":
        data["options"] = {"text": sp.message}
    return PuzzleSpec.model_validate(data)


def _side_type(name: str) -> Any:
    if name == "shift":
        from forge.puzzles.shift import Shift

        return Shift()
    if name == "numlock":
        from forge.puzzles.numlock import NumLock

        return NumLock()
    if name == "sudoku":
        from forge.puzzles.sudoku import Sudoku

        return Sudoku()
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
    lock: dict[str, Any] = field(default_factory=dict)

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
        out += [(f"chapter {ch.no} message", sp.message) for sp in ch.side if sp.message]
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
    if not MIN_SUSPECTS <= len(frame.suspects) <= MAX_SUSPECTS:
        p.append(f"need {MIN_SUSPECTS}-{MAX_SUSPECTS} suspects, got {len(frame.suspects)}")
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
        obj = ch.object.strip().lower()
        tag = f"chapter {ch.no}"
        if obj not in ICONS:
            p.append(f"{tag}: no picture for object {ch.object!r} (use {', '.join(ICONS)})")
            continue
        if obj in seen:
            p.append(f"{tag}: object {obj!r} already used in chapter {seen[obj]}")
        seen[obj] = ch.no
        if ch.shape not in SHAPES:
            p.append(f"{tag}: unknown cell shape {ch.shape!r} (use {', '.join(SHAPES)})")
        else:
            try:
                plan_tiling(ch.shape, code_of(ch), cbn_spec(frame, ch, i))
            except GenerationError as e:
                p.append(f"{tag}: {e}")
        if len(ch.side) != 2:
            p.append(f"{tag}: needs exactly 2 side puzzles, got {len(ch.side)}")
        if len(ch.hints) != 3:
            p.append(f"{tag}: needs 3 hint tiers, got {len(ch.hints)}")
        for sp in ch.side:
            kw = sp.keyword.upper()
            if not keyword_ok(sp.type, kw, _kids(frame.audience)):
                want = "2-4 digits" if sp.type in NUMBER_TYPES else "one word of 3-12 letters"
                p.append(f"{tag}: keyword {sp.keyword!r} must be {want} for a {sp.type}")
                continue
            if sp.type == "shift":
                words = re.findall(r"[A-Z]+", sp.message.upper())
                others = {k.upper() for d in ch.decoys for k in d.keywords} - {kw}
                both = sorted(others & set(words))
                if both:
                    p.append(f"{tag}: the message also contains the decoy keyword {both[0]}")
                if kw not in words or len(words) < 6:
                    p.append(
                        f"{tag}: the cipher needs a message of at least 6 words from the "
                        f"case that contains {kw}"
                    )
            if kw in keys:
                p.append(f"{tag}: keyword {kw} already used in chapter {keys[kw]}")
            keys[kw] = ch.no
            if sp.type not in NUMBER_TYPES and is_blocked(kw.lower()):
                p.append(f"{tag}: keyword {kw} is on the blocklist")
            if deep:
                try:
                    _generate(_side_type(sp.type), side_spec(frame, sp, i), seed + 97 * ch.no, 3)
                except GenerationError as e:
                    p.append(f"{tag}: {sp.type} cannot produce keyword {kw} ({e})")
        if len(ch.side) == 2:
            p.extend(_card_problems(ch))
        p.extend(_leaks(ch))
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
        lr = logic_lock.check_logic(
            frame.suspects,
            frame.answer,
            [(f"ch{ch.no}", ch.clue) for ch in frame.chapters],
            {
                f"ch{ch.no}": [(_row_label(_key(d.object, d.keywords)), d.clue) for d in ch.decoys]
                for ch in frame.chapters
            },
            frame.answer_field,
        )
        rep.lock = {"removed": lr.removed, "left_after": lr.left_after, "ok": lr.ok}
        p.extend(x for x in lr.problems if x not in p)
        if lr.solutions != nr.solutions or sorted(lr.redundant) != sorted(nr.redundant):
            p.append("the two logic solvers disagree about this case")
    except (necessity.CaseError, logic_lock.LockError, KeyError) as e:
        p.append(f"clue logic: {e}")
    p.extend(case_graph(frame).problems())
    return rep


def _card_problems(ch: Chapter) -> list[str]:
    """The card must need all three answers of the chapter to find the true row."""
    out: list[str] = []
    tag = f"chapter {ch.no}"
    obj, kws = _key(ch.object, [sp.keyword for sp in ch.side])
    keys = [k for k, _m, _r, _t in card_rows(ch)]
    if len(set(keys)) != len(keys):
        out.append(f"{tag}: two rows of the evidence card have the same object and keywords")
    for d in ch.decoys:
        if d.object.strip().lower() not in ICONS:
            out.append(f"{tag}: decoy object {d.object!r} has no picture")
        if len(d.keywords) != 2 or not all(
            re.fullmatch(r"[A-Za-z]{3,12}|[0-9]{2,4}", k) for k in d.keywords
        ):
            out.append(f"{tag}: decoy rows need two keywords (one word or one number each)")
    dec = [_key(d.object, d.keywords) for d in ch.decoys]
    if not any(o != obj and k == kws for o, k in dec):
        out.append(f"{tag}: add a decoy row with another object and the same two keywords")
    for kw in sorted(kws):
        if not any(o == obj and kw not in k and len(k & kws) == 1 for o, k in dec):
            out.append(f"{tag}: add a decoy row with the same object where only {kw} differs")
    return out


def _answers(ch: Chapter) -> list[str]:
    return [ch.object.upper(), *(sp.keyword.upper() for sp in ch.side)]


def _leaks(ch: Chapter) -> list[str]:
    """Answers the reader must work for may not be printed in the chapter's own text."""
    out = []
    words = _answers(ch)
    texts = [("title", ch.title), ("story", ch.story), ("card intro", ch.evidence)]
    texts += [(f"hint {i}", h) for i, h in enumerate(ch.hints[:2], 1)]  # hint 3 is the answer
    texts += [("puzzle intro", sp.intro) for sp in ch.side]
    for where, text in texts:
        for w in words:
            if re.search(rf"\b{re.escape(w)}S?\b", text or "", re.I):
                out.append(f"chapter {ch.no}: {where} gives away the answer {w}")
    return out


def case_graph(frame: CaseFrame) -> CausalGraph:
    """Causal graph in page order: story -> 3 puzzles -> evidence card ... -> final deduction."""
    g = CausalGraph()
    cards = []
    for ch in frame.chapters:
        n = ch.no
        g.add(f"story{n}", "story")
        g.add(f"picture{n}", "puzzle", (f"story{n}",))
        side = [g.add(f"keyword{n}.{k}", "puzzle", (f"story{n}",)).id for k in (1, 2)]
        cards.append(g.add(f"card{n}", "evidence", (f"picture{n}", *side[: len(ch.side)])).id)
    g.add("final", "final", tuple(cards))
    return g


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


def _solved_keyword(sp: SidePuzzle, pz: Puzzle) -> str | None:
    """Keyword a reader gets from a side puzzle: the independent solver must agree with the stored
    solution, and where the solver output shows the keyword itself it is read from there."""
    pt = _side_type(sp.type)
    if not pt.verify(pz).ok:
        return None
    sol = pt.solve(pz).solution or {}
    seen = sol.get("code")
    if sp.type == "shift":  # the keyword must be a word of the message the solver decoded
        plain = str(sol.get("plain") or "").split()
        return str(pz.token) if pz.token in plain else None
    token = str(pz.token or "").upper()
    return token if seen is None or str(seen).upper() == token else None


@dataclass
class ReaderRun:
    problems: list[str] = field(default_factory=list)
    left_after: list[int] = field(default_factory=list)
    answer: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def simulate_reader(frame: CaseFrame, puzzles: list[ChapterPuzzles]) -> ReaderRun:
    """Play the finished book in page order using only what the solvers produce.

    Per chapter: read the picture from the solved mosaic (two readers must agree), solve both side
    puzzles, find the card row for exactly these three answers, cross out suspects. One suspect
    may remain only after the last chapter. Leaving out any one answer must not identify a row."""
    run = ReaderRun()
    left = list(frame.suspects)
    cb = ColorByNumber()
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        tag = f"chapter {ch.no}"
        colours = (cb.solve(cp.cbn).solution or {"colors": [[]]})["colors"]
        t = tiling_of(cp.cbn)
        seen = {tiling.read_raster(t, colours[0]), tiling.read_centres(t, colours[0])}
        if len(seen) != 1 or not next(iter(seen)).startswith("@"):
            run.problems.append(f"{tag}: the mosaic picture is not readable ({sorted(seen)})")
            break
        obj = next(iter(seen))[1:]
        kws = [_solved_keyword(sp, pz) for sp, pz in zip(ch.side, cp.side, strict=True)]
        if None in kws:
            run.problems.append(f"{tag}: a side puzzle does not give its keyword")
            break
        mine = (obj, frozenset(str(k) for k in kws))
        rows = card_rows(ch)
        hit = [r for r in rows if r[0] == mine]
        if len(hit) != 1 or not hit[0][3]:
            run.problems.append(f"{tag}: the solved answers do not select the true card row")
            break
        for part in ("object", *sorted(mine[1])):
            same = [
                r
                for r in rows
                if (part == "object" or r[0][0] == obj) and (mine[1] - {part}) <= r[0][1]
            ]
            if len(same) < 2:
                run.problems.append(f"{tag}: the card can be read without solving for {part}")
        rule = hit[0][2]
        left = [s for s in left if rule is None or necessity.holds(rule, s)]
        run.left_after.append(len(left))
    run.answer = [str(s[frame.answer_field]) for s in left]
    if not run.problems:
        if run.answer != [frame.answer]:
            run.problems.append(f"reader ends with {run.answer}, not the declared answer")
        if any(k <= 1 for k in run.left_after[:-1]):
            run.problems.append("reader knows the culprit before the last chapter")
    return run


# --- layout ---------------------------------------------------------------------------------


def _para(text: str) -> list[dict[str, Any]]:
    return [{"kind": "paragraph", "text": t.strip()} for t in text.split("\n") if t.strip()]


def _evidence_rows(ch: Chapter) -> list[str]:
    return [f"{_row_label(k)}  →  {m}" for k, m, _r, _t in card_rows(ch)]


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
                        "Colour the mosaic by number. A picture of the evidence appears.",
                        "Solve the two side puzzles. Each keyword describes that evidence.",
                        "Open the evidence card. Find the line with YOUR picture and "
                        "YOUR two keywords. Only that line is true.",
                        "Write the evidence, both keywords and the fact in the Code Log.",
                        "After the last chapter, cross out every suspect who does not fit "
                        "a fact. One name stays.",
                        "No suspect left, or more than one? One of your answers is wrong: "
                        "go back and check.",
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
        f"Chapter {ch.no}:   evidence __________   it is __________ and __________   "
        "fact: ______________________________"
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
        add(Page(kind="puzzle", title=f"Chapter {ch.no}: The Hidden Evidence", blocks=front.blocks))
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
                        "text": "Only the line with your picture and both of your keywords "
                        "is true. Note its fact in the Code Log.",
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
            {
                "kind": "paragraph",
                "text": f"Evidence: {ch.object.upper()}. Keywords: {keys}. Fact: {ch.meaning}",
            }
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
            "suspects_left_after_each_chapter": rep.lock.get("left_after", []),
            "suspects_removed_per_clue": rep.lock.get("removed", {}),
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
    run = simulate_reader(frame, puzzles)
    if not run.ok:
        raise necessity.CaseError("reader simulation failed: " + "; ".join(run.problems))
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
    man["reader_sim"] = {"ok": run.ok, "left_after": run.left_after}
    (out / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    (out / "art_requests.json").write_text(json.dumps(art, indent=2), encoding="utf-8")
    if render:
        doc = make_layout(
            title=frame.title, subtitle=frame.subtitle, trim=trim, pages=pages, min_pages=0
        )
        render_pdf(doc, out / "interior.pdf", files=files)
    return man
