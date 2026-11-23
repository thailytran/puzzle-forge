"""Adventure line: case frame -> checked frame -> verified puzzles -> reader run (ROADMAP P9.1).

An Adventure book (owner 2026-11-20) is a story in chapters. Every chapter is a room:
  * a story page with a line-art vignette,
  * a full-page line-art search scene with 12-20 hidden objects (icon + name in a side column),
  * Puzzle A: its answer word gives the chapter's KEY LETTER (the word's first letter),
  * Puzzle B: its answer digit gives the KEY SLOT (1..N) in the lock of the final door.
After the last chapter the reader writes each letter into its slot; the slots spell the FINAL WORD,
which is also the Case Vault answer (`unlock_code`, MYSTERY_DESIGN.md section 17).

Golden rules (CLAUDE.md): the frame only *declares* answers; code builds every puzzle from them,
an independent solver re-solves it, and `simulate_reader` plays the book with solver output only.
The logic lock (`lock_check`) is the mystery rule "every clue needed, one answer" over the
candidate space of all N-letter codes: all keys -> exactly the final word; any key (or any key
letter) left out -> more than one code fits.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from forge.adventure.objects import letters, norm, object_problems
from forge.core.models import Audience, Level, Puzzle, PuzzleSpec
from forge.mystery.cbn_case import LEVELS, UNSAFE, _generate, _side_type, keyword_ok
from forge.vault.rules import answer_problems

# Puzzle A: types whose solved answer is a WORD (frame labels -> code type)
A_TYPES: dict[str, tuple[str, ...]] = {
    "scramble": ("word scramble", "scramble"),
    "maze": ("letter maze", "maze"),
    "cryptogram": ("cryptogram",),
    "wordsearch": ("word search", "wordsearch"),
    "shift": ("shift cipher", "shift", "code breaker"),
    "pigpen": ("pigpen", "pigpen cipher", "secret symbols"),
    "starbattle": ("star battle", "star search", "starbattle"),
    "lightup": ("lantern lights", "light up", "lightup"),
    "wordladder": ("word ladder", "wordladder"),
    "wordoku": ("wordoku", "letter vault"),
}
# Puzzle B: types whose solved answer is ONE DIGIT (the slot)
B_TYPES: dict[str, tuple[str, ...]] = {
    "numlock": ("number lock", "numlock"),
    "sudoku": ("sudoku (6\u00d76)", "sudoku (6x6)", "sudoku 6x6", "sudoku"),
}
MESSAGE_TYPES = ("shift", "pigpen", "cryptogram")  # answer = LAST word of the decoded message
LABELS = {
    "scramble": "Word Scramble",
    "maze": "Letter Maze",
    "cryptogram": "Cryptogram",
    "wordsearch": "Word Search",
    "shift": "Shift Cipher",
    "pigpen": "Secret Symbols",
    "starbattle": "Star Search",
    "lightup": "Lantern Lights",
    "wordladder": "Word Ladder",
    "wordoku": "Letter Vault",
    "numlock": "Number Lock",
    "sudoku": "Sudoku 6\u00d76",
}
CHAPTERS = {"adult": (6, 10), "kids": (3, 8)}
SUDOKU_SLOT_CELL = [(0, 0)]  # 6x6 sudoku: the shaded corner cell is the slot digit


def code_type(label: str, part: str = "a") -> str:
    """Frame label ("Word Scramble", "scramble") -> code type; '' when the type is unknown."""
    table = A_TYPES if part == "a" else B_TYPES
    low = norm(label)
    for code, names in table.items():
        if low == code or low in names:
            return code
    return ""


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PuzzleA(_M):
    type: str
    answer: str
    message: str = ""  # shift / pigpen / cryptogram: the text to decode, ending with the answer
    intro: str = ""  # one flavour line on the puzzle page (never the answer)
    rule: str = ""
    explain: str = ""  # answer page: how the answer is reached


class PuzzleB(_M):
    type: str
    digit: int
    intro: str = ""
    rule: str = ""
    explain: str = ""


class KeyPiece(_M):
    letter: str
    slot: int


class AdvChapter(_M):
    no: int
    title: str
    room: str
    tags: list[str] = Field(default_factory=list)  # catalog tags for `pick_objects`
    story: str
    vignette: str = ""  # picture brief for the story vignette (else derived from the story)
    scene: str = ""  # picture brief for the full-page search scene (else derived)
    hidden_objects: list[str]
    captions: dict[str, str] = Field(default_factory=dict)  # object -> one line (ChatGPT, optional)
    puzzle_a: PuzzleA
    puzzle_b: PuzzleB
    key: KeyPiece
    teaser: str = ""  # one line on the key page that pulls the reader on


class CastMember(_M):
    id: str
    name: str
    role: str = ""
    look: str
    outfit: str = ""


class FinalLock(_M):
    word: str
    slots: dict[str, str]
    rule: str = ""
    intro: str = ""  # final challenge page text


class AdventureFrame(_M):
    id: str
    line: str = "ADV"
    title: str
    subtitle: str = ""
    audience: Audience = "adult"
    season: str = ""
    inspired_by: dict[str, Any] = Field(default_factory=dict)
    setting: str
    cast: list[CastMember] = Field(default_factory=list)
    prologue_title: str = "Prologue"
    prologue: str = ""
    chapters: list[AdvChapter]
    final: FinalLock
    epilogue_title: str = "Epilogue"
    epilogue: str = ""
    art_style: str = ""
    guardrails: list[str] = Field(default_factory=list)
    page_plan: dict[str, Any] = Field(default_factory=dict)
    listing: dict[str, Any] = Field(default_factory=dict)


def load_frame(path: Any) -> AdventureFrame:
    return AdventureFrame.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _kids(frame: AdventureFrame) -> bool:
    return frame.audience.startswith("kids")


# --- logic lock --------------------------------------------------------------------------------


@dataclass
class LockReport:
    count_all: int = 0  # codes that fit with every key (must be 1)
    drop_key: dict[int, int] = field(default_factory=dict)  # chapter -> codes without its key
    drop_letter: dict[int, int] = field(default_factory=dict)  # chapter -> codes without its letter
    drop_slot: dict[int, int] = field(default_factory=dict)  # chapter -> codes without its slot
    word: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "count_all": self.count_all,
            "without_key": self.drop_key,
            "without_letter": self.drop_letter,
            "without_slot": self.drop_slot,
        }


def count_codes(n: int, placed: dict[int, str], floating: list[str], alphabet: int = 26) -> int:
    """Number of N-letter codes consistent with what the reader knows.

    `placed`: slot -> letter (both halves of the key solved); `floating`: letters whose slot is
    unknown (Puzzle B not solved). Unknown slots take the floating letters in any order and any
    letter elsewhere. Distinct codes are counted (equal floating letters are not told apart)."""
    free = n - len(placed)
    if len(floating) > free:
        return 0
    k = len(floating)
    ways = math.perm(free, k)
    for c in {x: floating.count(x) for x in floating}.values():  # identical letters
        ways //= math.factorial(c)
    return ways * alphabet ** (free - k)


def lock_check(frame: AdventureFrame) -> LockReport:
    n = len(frame.chapters)
    keys = {ch.no: (ch.key.slot, ch.key.letter.upper()) for ch in frame.chapters}
    rep = LockReport(word=frame.final.word.upper())
    rep.count_all = count_codes(n, {s: L for s, L in keys.values()}, [])
    for no, (_slot, letter) in keys.items():
        rest = {s: L for k, (s, L) in keys.items() if k != no}
        rep.drop_key[no] = count_codes(n, rest, [])
        rep.drop_letter[no] = count_codes(n, rest, [])  # slot known, letter unknown: any letter
        rep.drop_slot[no] = count_codes(n, rest, [letter])
    return rep


# --- frame check -------------------------------------------------------------------------------


@dataclass
class FrameReport:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lock: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems

    def feedback(self) -> str:
        return "\n".join(f"- {p}" for p in self.problems)


def _texts_until(frame: AdventureFrame, no: int) -> list[tuple[str, str]]:
    """Every reader-facing text printed before Puzzle A of chapter `no` is solved."""
    out = [("subtitle", frame.subtitle), ("prologue", frame.prologue), ("setting", frame.setting)]
    for ch in frame.chapters:
        if ch.no > no:
            break
        out += [(f"chapter {ch.no} story", ch.story), (f"chapter {ch.no} title", ch.title)]
        out += [(f"chapter {ch.no} caption", c) for c in ch.captions.values()]
        out += [(f"chapter {ch.no} object", o) for o in ch.hidden_objects]
        if ch.no < no:
            continue
        out += [(f"chapter {ch.no} puzzle A intro", ch.puzzle_a.intro)]
        out += [(f"chapter {ch.no} puzzle B intro", ch.puzzle_b.intro)]
    return out


def _has_word(text: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\w*", text, re.I))


def check_frame(frame: AdventureFrame, seed: int = 1, deep: bool = True) -> FrameReport:
    rep = FrameReport()
    p, w = rep.problems, rep.warnings
    n = len(frame.chapters)
    lo, hi = CHAPTERS["kids" if _kids(frame) else "adult"]
    if not lo <= n <= hi:
        p.append(f"{n} chapters; this audience needs {lo}-{hi}")
    if [ch.no for ch in frame.chapters] != list(range(1, n + 1)):
        p.append("chapters must be numbered 1..N in order")
    word = frame.final.word.upper()
    if len(word) != n:
        p.append(f"final word {word!r} has {len(word)} letters for {n} chapters (one key each)")
    p += [f"final word: {x}" for x in answer_problems("unlock_code", [], [word], kids=_kids(frame))]
    slots = sorted(ch.key.slot for ch in frame.chapters)
    if slots != list(range(1, n + 1)):
        p.append(f"key slots {slots} must use every slot 1..{n} once")
    declared = {int(k): v.upper() for k, v in frame.final.slots.items()}
    for ch in frame.chapters:
        tag = f"chapter {ch.no}"
        a, b, key = ch.puzzle_a, ch.puzzle_b, ch.key
        ta, tb = code_type(a.type, "a"), code_type(b.type, "b")
        ans = a.answer.strip().upper()
        if not ta:
            p.append(
                f"{tag}: puzzle A type {a.type!r} cannot give a verified word yet "
                f"(use one of {sorted(LABELS[t] for t in A_TYPES)})"
            )
        elif not keyword_ok(ta, ans, _kids(frame)) and ta not in ("scramble", "cryptogram"):
            p.append(f"{tag}: answer {ans!r} does not fit a {LABELS[ta]} puzzle")
        if not re.fullmatch(r"[A-Z]{3,12}", ans):
            p.append(f"{tag}: answer {ans!r} must be 3-12 letters")
        if ta in MESSAGE_TYPES:
            words = re.findall(r"[A-Z]+", a.message.upper())
            if not words or words[-1] != ans:
                p.append(f"{tag}: the {LABELS[ta]} message must end with the answer {ans!r}")
            if len(words) < 5:
                p.append(f"{tag}: the {LABELS[ta]} message needs at least 5 words")
        if not tb:
            p.append(
                f"{tag}: puzzle B type {b.type!r} cannot give a verified digit "
                f"(use Number Lock or Sudoku 6\u00d76)"
            )
        if not 1 <= b.digit <= n:
            p.append(f"{tag}: puzzle B digit {b.digit} is not a slot 1..{n}")
        if tb == "sudoku" and not 1 <= b.digit <= 6:
            p.append(f"{tag}: a 6\u00d76 sudoku gives digits 1-6, not {b.digit}")
        if key.letter.upper() != ans[:1]:
            p.append(f"{tag}: key letter {key.letter!r} is not the first letter of {ans!r}")
        if key.slot != b.digit:
            p.append(f"{tag}: key slot {key.slot} differs from puzzle B digit {b.digit}")
        if declared.get(key.slot) != key.letter.upper():
            p.append(f"{tag}: final.slots[{key.slot}] must be {key.letter.upper()!r}")
        if 1 <= key.slot <= len(word) and word[key.slot - 1] != key.letter.upper():
            p.append(
                f"{tag}: slot {key.slot} of {word!r} is {word[key.slot - 1]!r}, "
                f"the key gives {key.letter.upper()!r}"
            )
        for where, text in _texts_until(frame, ch.no):
            if text and _has_word(text, ans):
                p.append(f"{tag}: answer {ans!r} is printed in the {where} (leak)")
        p += [f"{tag}: {x}" for x in object_problems(ch.hidden_objects, [ans])]
        for o in ch.captions:
            if norm(o) not in {norm(x) for x in ch.hidden_objects}:
                p.append(f"{tag}: caption for {o!r}, which is not a hidden object")
    seen: dict[str, int] = {}
    for ch in frame.chapters:
        for o in ch.hidden_objects:
            if norm(o) in seen:
                w.append(f"object {norm(o)!r} is hidden in chapters {seen[norm(o)]} and {ch.no}")
            seen.setdefault(norm(o), ch.no)
    for where, text in _texts_until(frame, n):
        if text and _has_word(text, word):
            p.append(f"final word {word!r} is printed in the {where} (leak)")
        if text and UNSAFE.search(text):
            p.append(f"{where}: unsafe word {UNSAFE.search(text).group(0)!r}")  # type: ignore[union-attr]
    lock = lock_check(frame)
    rep.lock = lock.as_dict()
    if not p:
        if lock.count_all != 1:
            p.append(f"logic lock: {lock.count_all} codes fit every key (must be 1)")
        for no, c in lock.drop_key.items():
            if c < 2:
                p.append(f"logic lock: chapter {no}'s key is not needed ({c} code without it)")
        for no, c in lock.drop_letter.items():
            if c < 2:
                p.append(f"logic lock: chapter {no}'s letter is not needed")
        elim = [no for no, c in lock.drop_slot.items() if c < 2]
        if elim:
            w.append(
                "logic lock: a Puzzle B slot can be found by elimination once every other key "
                f"is known (chapters {elim}); the letter is still needed (inherent to an "
                "N-slot lock)"
            )
    if deep and not p:
        try:
            puzzles = build_puzzles(frame, seed)
        except Exception as e:  # the report names what could not be built
            p.append(f"puzzles: {e}")
        else:
            run = simulate_reader(frame, puzzles)
            p += [f"reader: {x}" for x in run.problems]
    return rep


# --- puzzles -----------------------------------------------------------------------------------


@dataclass
class ChapterPuzzles:
    a: Puzzle
    b: Puzzle


def _level(frame: AdventureFrame, idx: int) -> Level:
    return "easy" if _kids(frame) else LEVELS[min(idx, len(LEVELS) - 1)]


def spec_a(frame: AdventureFrame, ch: AdvChapter, idx: int) -> PuzzleSpec:
    t = code_type(ch.puzzle_a.type, "a")
    ans = ch.puzzle_a.answer.strip().upper()
    data: dict[str, Any] = {"type": t, "level": _level(frame, idx), "audience": frame.audience}
    if t == "maze":
        data["constraints"] = [{"kind": "path_letters", "seq": ans}]
    elif t == "wordsearch":  # the room's own objects are the word list; leftovers spell the answer
        data["words"] = [letters(o) for o in ch.hidden_objects if 3 <= len(letters(o)) <= 12]
        data["constraints"] = [{"kind": "hidden_message", "text": ans}]
    else:
        data["constraints"] = [{"kind": "answer_is", "word": ans}]
    if t == "scramble":
        data["theme"] = frame.season or "winter"
    if t in MESSAGE_TYPES:
        data["options"] = {"text": ch.puzzle_a.message.upper()}
    if t == "lightup":
        data["options"] = {"letters": True}
    return PuzzleSpec.model_validate(data)


def spec_b(frame: AdventureFrame, ch: AdvChapter, idx: int) -> PuzzleSpec:
    t = code_type(ch.puzzle_b.type, "b")
    digit = str(ch.puzzle_b.digit)
    level = _level(frame, idx)
    data: dict[str, Any] = {"type": t, "level": level, "audience": frame.audience}
    if t == "sudoku":
        data["options"] = {"size": 6}
        data["level"] = "easy" if level == "easy" else "medium"
        data["constraints"] = [{"kind": "shaded_cells", "cells": SUDOKU_SLOT_CELL, "expect": digit}]
    else:
        data["constraints"] = [{"kind": "answer_is", "word": digit}]
    return PuzzleSpec.model_validate(data)


def puzzle_type(name: str) -> Any:
    if name == "scramble":
        from forge.puzzles.scramble import Scramble

        return Scramble()
    if name == "cryptogram":
        from forge.puzzles.cryptogram import Cryptogram

        return Cryptogram()
    if name == "wordsearch":
        from forge.puzzles.wordsearch import WordSearch

        return WordSearch()
    return _side_type(name)


def build_puzzles(frame: AdventureFrame, seed: int) -> list[ChapterPuzzles]:
    out = []
    for i, ch in enumerate(frame.chapters):
        base = seed + 10007 * ch.no
        a = _generate(puzzle_type(code_type(ch.puzzle_a.type, "a")), spec_a(frame, ch, i), base)
        b = _generate(
            puzzle_type(code_type(ch.puzzle_b.type, "b")), spec_b(frame, ch, i), base + 31
        )
        out.append(ChapterPuzzles(a, b))
    return out


def solved_word(t: str, pz: Puzzle) -> str | None:
    """Answer word a reader gets from Puzzle A, read from the independent solver's output."""
    pt = puzzle_type(t)
    if not pt.verify(pz).ok:
        return None
    sol = pt.solve(pz).solution or {}
    if t == "scramble":
        bonus = sol.get("bonus") or []
        return str(bonus[0]).upper() if bonus else None
    if t == "wordsearch":
        return str(sol.get("leftover") or "").upper() or None
    if t in MESSAGE_TYPES:
        plain = sol.get("plain") or sol.get("text")
        if plain is None and t == "cryptogram":  # solver proved one decoding: the stored plain
            plain = " ".join(str(q.get("plain", "")) for q in pz.solution.get("quotes", []))
        words = re.findall(r"[A-Z]+", str(plain or "").upper())
        return words[-1] if words else None
    seen = sol.get("code", sol.get("word"))
    token = str(pz.token or "").upper()
    return token if seen is None or str(seen).upper() == token else None


def solved_digit(t: str, pz: Puzzle) -> int | None:
    pt = puzzle_type(t)
    if not pt.verify(pz).ok:
        return None
    sol = pt.solve(pz).solution or {}
    if t == "sudoku":
        grid = sol.get("grid") or sol.get("rows") or pz.solution.get("grid")
        try:
            r, c = SUDOKU_SLOT_CELL[0]
            return int(str(grid[r][c]))
        except (TypeError, IndexError, ValueError):
            return None
    code = str(sol.get("code") or "")
    return int(code) if code.isdigit() else None


@dataclass
class ReaderRun:
    problems: list[str] = field(default_factory=list)
    slots: dict[int, str] = field(default_factory=dict)
    word: str = ""

    @property
    def ok(self) -> bool:
        return not self.problems


def simulate_reader(frame: AdventureFrame, puzzles: list[ChapterPuzzles]) -> ReaderRun:
    """Play the book in page order with solver output only, then read the lock."""
    run = ReaderRun()
    n = len(frame.chapters)
    for ch, cp in zip(frame.chapters, puzzles, strict=True):
        tag = f"chapter {ch.no}"
        wd = solved_word(code_type(ch.puzzle_a.type, "a"), cp.a)
        dg = solved_digit(code_type(ch.puzzle_b.type, "b"), cp.b)
        if not wd:
            run.problems.append(f"{tag}: puzzle A does not give its answer word")
            continue
        if dg is None or not 1 <= dg <= n:
            run.problems.append(f"{tag}: puzzle B does not give a slot 1..{n}")
            continue
        if dg in run.slots:
            run.problems.append(f"{tag}: slot {dg} is already filled")
        run.slots[dg] = wd[0]
        if len(run.slots) == n and ch.no != n:
            run.problems.append("the lock is complete before the last chapter")
    run.word = "".join(run.slots.get(i, "?") for i in range(1, n + 1))
    if not run.problems and run.word != frame.final.word.upper():
        run.problems.append(f"the lock reads {run.word!r}, not {frame.final.word.upper()!r}")
    return run
