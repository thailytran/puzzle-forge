"""Layout document: the ordered pages Python hands to `templates/typst/book.typ`.

Block kinds understood by the template:
  heading {text, level}        paragraph {text}        list {items}
  spacer {height_in}           image {path, width_in}
  letter_grid {rows: [[str|null]], cell_in, font_pt, borders?, highlights?: [[r1,c1,r2,c2]]}
  word_list {words, columns, font_pt}
  toc {entries: [{title, page}]}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from forge.layout.trim import TRIMS, Margins, margins_for, pad_page_count

PageKind = Literal["title", "copyright", "text", "puzzle", "solutions", "notes", "blank"]


class Fonts(BaseModel):
    body: str = "Libertinus Serif"
    sans: str = "Atkinson Hyperlegible"
    mono: str = "Courier Prime"


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PageKind
    title: str | None = None
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    header: bool = True
    number: bool = True


class LayoutDoc(BaseModel):
    title: str
    subtitle: str = ""
    author: str = ""
    trim: str
    width_in: float
    height_in: float
    margins: dict[str, float]
    fonts: Fonts = Field(default_factory=Fonts)
    base_size_pt: float = 11.0
    pages: list[Page]

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=1, ensure_ascii=False)


def pad_pages(pages: list[Page], min_pages: int | None = None) -> list[Page]:
    """Append "Notes" pages until the count is even (and ≥ KDP minimum by default)."""
    target = pad_page_count(len(pages), min_pages)
    return pages + [Page(kind="notes", title="Notes") for _ in range(target - len(pages))]


def make_layout(
    *,
    title: str,
    trim: str,
    pages: list[Page],
    subtitle: str = "",
    author: str = "",
    large_print: bool = False,
    min_pages: int | None = None,
) -> LayoutDoc:
    """Build a LayoutDoc with KDP-safe margins and an even page count."""
    if trim not in TRIMS:
        raise ValueError(f"unknown trim {trim!r}; choose one of {sorted(TRIMS)}")
    padded = pad_pages(pages, min_pages)
    m: Margins = margins_for(len(padded))
    t = TRIMS[trim]
    return LayoutDoc(
        title=title,
        subtitle=subtitle,
        author=author,
        trim=trim,
        width_in=t.width_in,
        height_in=t.height_in,
        margins={"inside": m.inside, "outside": m.outside, "top": m.top, "bottom": m.bottom},
        base_size_pt=16.0 if large_print else 11.0,
        pages=padded,
    )


def write_build_dir(doc: LayoutDoc, build_dir: Path, files: dict[str, bytes] | None = None) -> Path:
    """Write templates + layout.json + side files into `build_dir`; return main .typ path."""
    from forge.layout.typst_runner import TEMPLATE_DIR

    build_dir.mkdir(parents=True, exist_ok=True)
    for tpl in TEMPLATE_DIR.glob("*.typ"):
        (build_dir / tpl.name).write_text(tpl.read_text(encoding="utf-8"), encoding="utf-8")
    (build_dir / "layout.json").write_text(doc.to_json(), encoding="utf-8")
    for name, data in (files or {}).items():
        target = build_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return build_dir / "book.typ"


def render_pdf(doc: LayoutDoc, out_pdf: Path, files: dict[str, bytes] | None = None) -> Path:
    """Render `doc` to `out_pdf` (build files go to `<out_dir>/build/`)."""
    from forge.layout.typst_runner import compile_pdf

    main = write_build_dir(doc, out_pdf.parent / "build", files)
    return compile_pdf(main, out_pdf, root=main.parent)
