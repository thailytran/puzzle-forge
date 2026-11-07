"""L3 — section / whole-book checks (docs/QA_SPEC.md §3)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forge.book.plan import plan_book
from forge.core.book import BookSpec
from forge.core.models import LEVELS
from forge.layout.trim import load_kdp_rules
from forge.qa.checks import Finding, check
from forge.qa.l2 import layout, pdf
from forge.wordlists import available_themes, theme_words
from forge.wordlists.dictionary import common_words, words

PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX|Lorem|ipsum)\b|\{[^}]*\}|<[a-z_]+>", re.I)
PROSE_KINDS = ("paragraph", "heading", "list", "toc")
MATTER_MARKERS = {
    "copyright": "Copyright",
    "how_to_play": "How to Play",
    "table_of_contents": "Contents",
    "solutions": "Solutions",
    "about": "About This Book",
    "thank_you": "Thank You",
}


def _spec(ctx: Any) -> BookSpec:
    return BookSpec.model_validate(ctx.manifest["spec"])


@check(
    "L3.counts",
    "BLOCKER",
    "Page and puzzle counts match the spec; even page count within KDP limits",
)
def counts(ctx: Any) -> list[Finding]:
    spec = _spec(ctx)
    out = []
    n_pages = len(pdf(ctx).pages)
    n_puz = len(ctx.manifest["puzzles"])
    rules = load_kdp_rules()
    if n_puz != spec.book.content_pages:
        out.append(
            Finding(
                message=f"{n_puz} puzzles, spec asks {spec.book.content_pages}",
                evidence={"measured": n_puz, "expected": spec.book.content_pages},
            )
        )
    if n_pages != ctx.manifest["page_count"]:
        out.append(Finding(message=f"PDF {n_pages} pages, manifest {ctx.manifest['page_count']}"))
    if n_pages % 2:
        out.append(Finding(message=f"odd page count {n_pages}", evidence={"pages": n_pages}))
    if not rules.min_pages <= n_pages <= rules.max_pages:
        out.append(
            Finding(message=f"{n_pages} pages outside KDP {rules.min_pages}-{rules.max_pages}")
        )
    return out


@check("L3.distribution", "MAJOR", "Type mix and difficulty curve follow the mode")
def distribution(ctx: Any) -> list[Finding]:
    spec = _spec(ctx)
    out = []
    plan = plan_book(spec)
    rows = ctx.manifest["puzzles"]
    for s, row in zip(plan, rows, strict=False):
        if (s.type, s.level) != (row["type"], row["level"]):
            out.append(
                Finding(
                    message=f"#{row['n']}: {row['type']}/{row['level']} "
                    f"but plan says {s.type}/{s.level}",
                    evidence={"puzzle_id": row["id"], "planned": [s.type, s.level]},
                )
            )
    if spec.puzzles.mode == "progressive":
        idx = [LEVELS.index(r["level"]) for r in rows]
        if idx != sorted(idx):
            out.append(Finding(message="progressive book is not easy → hard"))
    if spec.puzzles.mode == "mixed":
        for k in range(0, len(rows), 10):
            sec = rows[k : k + 10]
            if len(sec) == 10 and len({r["level"] for r in sec}) < min(
                3, len(spec.puzzles.distribution)
            ):
                out.append(Finding(message=f"section {k // 10 + 1} lacks a level mix"))
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


@check("L3.toc", "BLOCKER", "Table of contents points at the real pages")
def toc(ctx: Any) -> list[Finding]:
    pages = pdf(ctx).pages
    lay = layout(ctx)["pages"]
    toc_page = next((i for i, p in enumerate(lay) if p.get("title") == "Contents"), None)
    if toc_page is None:
        if "table_of_contents" in _spec(ctx).front_matter:
            return [Finding(message="spec asks for a table of contents but there is none")]
        return []
    entries = lay[toc_page]["blocks"][0]["entries"]
    out = []
    printed = _norm(pages[toc_page].text)
    for e in entries:
        title, page = e["title"], int(e["page"])
        if not re.search(re.escape(title) + r"[ .]*" + str(page) + r"\b", printed):
            out.append(
                Finding(
                    message=f"TOC line '{title} … {page}' not printed",
                    evidence={"page": toc_page + 1},
                )
            )
        target = _norm(pages[page - 1].text) if 0 < page <= len(pages) else ""
        expect = {"Puzzles": "#1 "}.get(title, title)
        if expect not in target:
            out.append(
                Finding(
                    message=f"TOC '{title}' → page {page}, which does not show it",
                    evidence={"page": page, "expected": expect},
                )
            )
    return out


@check("L3.matter", "MAJOR", "Required front/back matter present, including copyright")
def matter(ctx: Any) -> list[Finding]:
    spec = _spec(ctx)
    text = " ".join(_norm(p.text) for p in pdf(ctx).pages)
    out = []
    if spec.book.title not in text:
        out.append(Finding(message="book title not printed"))
    required = {*spec.front_matter, *spec.back_matter, "copyright"}
    for item in sorted(required):
        marker = MATTER_MARKERS.get(item)
        if marker and marker not in text:
            out.append(Finding(message=f"missing {item} ({marker!r})", evidence={"item": item}))
    return out


def _prose(ctx: Any) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, p in enumerate(layout(ctx)["pages"], 1):
        if p.get("title"):
            out.append((i, p["title"]))
        for b in p.get("blocks", []):
            k = b.get("kind")
            if k in ("paragraph", "heading"):
                out.append((i, b["text"]))
            elif k == "list":
                out += [(i, x) for x in b["items"]]
            elif k == "toc":
                out += [(i, e["title"]) for e in b["entries"]]
    spec = _spec(ctx)
    out += [(1, spec.book.title), (1, spec.book.subtitle)]
    return out


def _known() -> set[str]:
    known = set(common_words()) | set(words())
    for t in available_themes():
        known.update(theme_words(t))
    vocab = Path(__file__).resolve().parents[1] / "wordlists" / "vocabulary.txt"
    known.update(
        line.strip().upper()
        for line in vocab.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )
    return known


@check("L3.proofread", "MAJOR", "Spelling (dictionary) and basic grammar of all prose")
def proofread(ctx: Any) -> list[Finding]:
    known = _known()
    names = {
        w.upper() for w in re.findall(r"[A-Za-z]+", str(ctx.manifest["spec"]["book"]["author"]))
    }
    out = []
    for page, text in _prose(ctx):
        for word in re.findall(r"[A-Za-z]+(?:'[a-z]+)?", text):
            base = word.split("'")[0].upper()
            if len(base) > 1 and base not in known and base not in names:
                out.append(
                    Finding(
                        message=f"page {page}: unknown word {word!r}",
                        evidence={"page": page, "word": word},
                    )
                )
        rep = re.search(r"\b(\w+) \1\b", text, re.I)
        if rep:
            out.append(
                Finding(
                    message=f"page {page}: repeated word {rep.group(0)!r}", evidence={"page": page}
                )
            )
        if "  " in text:
            out.append(Finding(message=f"page {page}: double space", evidence={"page": page}))
    return out


@check("L3.placeholders", "BLOCKER", "No TODO / Lorem / {template} / <placeholder> text anywhere")
def placeholders(ctx: Any) -> list[Finding]:
    out = []
    for p in pdf(ctx).pages:
        m = PLACEHOLDER.search(p.text)
        if m:
            out.append(
                Finding(
                    message=f"page {p.number}: placeholder {m.group(0)!r}",
                    evidence={"page": p.number, "text": m.group(0)},
                )
            )
    for page, text in _prose(ctx):
        m = PLACEHOLDER.search(text)
        if m:
            out.append(
                Finding(
                    message=f"layout page {page}: placeholder {m.group(0)!r}",
                    evidence={"page": page, "text": m.group(0)},
                )
            )
    return out
