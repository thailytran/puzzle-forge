"""HALOSPARK Studio <-> Forge contract for the Adventure line (ROADMAP P9.4, Forge side).

Studio runs the AI and the owner review; Forge decides and verifies everything the reader needs.
`studio_package` writes the job folder Studio picks up:

  writing_brief.json   ChatGPT tasks + the exact JSON to return (stories, captions, intros,
                       explanations, listing copy). Answers are listed as FORBIDDEN words.
  art_requests.json    every picture: key, zone, aspect, brief, style, character refs
  selfcheck_prompt.txt Gemini vision prompt: where each hidden object is in a search scene
  review.json          owner tick list (object -> false) for the review UI

`merge_writing` takes ChatGPT's reply, copies only the allowed text fields into the frame and runs
the full frame check again, so a writer can never change an answer, a key or an object list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge.adventure.frame import AdventureFrame, FrameReport, check_frame
from forge.adventure.objects import norm

WRITING_FIELDS = ("story", "teaser", "captions")  # chapter fields ChatGPT may (re)write
PUZZLE_FIELDS = ("intro", "explain")


def writing_brief(frame: AdventureFrame) -> dict[str, Any]:
    forbidden = sorted(
        {ch.puzzle_a.answer.upper() for ch in frame.chapters} | {frame.final.word.upper()}
    )
    return {
        "book": frame.id,
        "title": frame.title,
        "audience": frame.audience,
        "rules": [
            "English book text, second person ('you'), warm and gently mysterious; no violence, "
            "no romance.",
            "Keep every name, room, cast look and plot point of the frame.",
            "Never print a FORBIDDEN word (any form) anywhere: they are puzzle answers.",
            "Never invent or change a puzzle answer, a key, a slot or a hidden object.",
            "Story: 100-130 words per chapter, 5-6 short paragraphs separated by \\n.",
            "Captions: one line per hidden object, at most 8 words, the object name first.",
            "Puzzle intros: one line, do not reveal the answer or the method beyond "
            "'decode / navigate / find the pattern'.",
            "Explain: two sentences per puzzle on how its answer is reached (answers given "
            "below are for this field only).",
            f"Listing copy must include: {frame.inspired_by.get('cover_line', '')!r}.",
        ],
        "forbidden": forbidden,
        "frame": {
            "setting": frame.setting,
            "cast": [c.model_dump() for c in frame.cast],
            "prologue": frame.prologue,
            "epilogue": frame.epilogue,
            "chapters": [
                {
                    "no": ch.no,
                    "title": ch.title,
                    "room": ch.room,
                    "story": ch.story,
                    "hidden_objects": [norm(o) for o in ch.hidden_objects],
                    "puzzle_a": {
                        "type": ch.puzzle_a.type,
                        "answer_for_explain_only": ch.puzzle_a.answer.upper(),
                    },
                    "puzzle_b": {
                        "type": ch.puzzle_b.type,
                        "digit_for_explain_only": ch.puzzle_b.digit,
                    },
                }
                for ch in frame.chapters
            ],
        },
        "return_json": {
            "chapters": [
                {
                    "no": ch.no,
                    "story": "...",
                    "teaser": "one line that pulls the reader to the next room",
                    "captions": {norm(o): "..." for o in ch.hidden_objects},
                    "puzzle_a": {"intro": "...", "explain": "..."},
                    "puzzle_b": {"intro": "...", "explain": "..."},
                }
                for ch in frame.chapters
            ],
            "listing": {
                "blurb": "<= 90 words",
                "promise": "one line",
                "bullets": ["5 bullets"],
                "etsy_title": "<= 140 characters",
                "shopify_description": "...",
            },
            "self_check": ["any sentence that may leak an answer or contradict the cast"],
        },
    }


SELFCHECK_PROMPT = """You drew this search scene. For each object in this list, find where you drew
it: {objects}.
Return ONLY JSON: [{{"name": "<object>", "x": <0-1>, "y": <0-1>, "r": <0-1>}}, ...] where x, y is
the centre of the object as a fraction of the picture width / height and r its radius as a fraction
of the width. Leave out an object you cannot find. Do not guess."""


def studio_package(frame: AdventureFrame, requests: list[dict[str, Any]], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "writing_brief.json": json.dumps(writing_brief(frame), indent=2, ensure_ascii=False),
        "art_requests.json": json.dumps(requests, indent=2, ensure_ascii=False),
        "selfcheck_prompt.txt": SELFCHECK_PROMPT,
        "review.json": json.dumps(
            {f"ch{ch.no}": {norm(o): False for o in ch.hidden_objects} for ch in frame.chapters},
            indent=2,
        ),
    }
    written = []
    for name, text in files.items():
        f = out / name
        if name == "review.json" and f.exists():  # never wipe the owner's ticks
            continue
        f.write_text(text, encoding="utf-8")
        written.append(f)
    return written


def merge_writing(
    frame: AdventureFrame, reply: dict[str, Any], seed: int = 1
) -> tuple[AdventureFrame, FrameReport]:
    """Apply ChatGPT's reply (text fields only) and re-check the whole frame."""
    data = frame.model_dump()
    by_no = {int(c.get("no", 0)): c for c in reply.get("chapters", [])}
    for ch in data["chapters"]:
        r = by_no.get(ch["no"]) or {}
        for k in WRITING_FIELDS:
            if r.get(k):
                ch[k] = r[k] if k != "captions" else {norm(o): str(t) for o, t in r[k].items()}
        for part in ("puzzle_a", "puzzle_b"):
            for k in PUZZLE_FIELDS:
                v = (r.get(part) or {}).get(k)
                if v:
                    ch[part][k] = str(v)
    if reply.get("listing"):
        data["listing"] = dict(reply["listing"])
    new = AdventureFrame.model_validate(data)
    rep = check_frame(new, seed, deep=False)
    blob = json.dumps(reply.get("listing") or {}).upper()
    for word in {ch.puzzle_a.answer.upper() for ch in new.chapters} | {new.final.word.upper()}:
        if word in blob:
            rep.problems.append(f"listing copy prints the answer {word!r} (leak)")
    for ch in new.chapters:  # explanations are printed only on the solutions pages: allowed
        n = len(ch.story.split())
        if not 60 <= n <= 170:
            rep.warnings.append(f"chapter {ch.no}: story has {n} words (aim 100-130)")
    return new, rep
