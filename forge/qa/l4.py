"""L4 — mystery / escape logic (docs/QA_SPEC.md §3 L4, MYSTERY_DESIGN.md §15)."""

from __future__ import annotations

from typing import Any

from forge.mystery.necessity import check_case
from forge.qa.checks import Finding, Skip, check


def _cases(ctx: Any) -> list[dict[str, Any]]:
    case = ctx.manifest.get("case")
    if not case:
        raise Skip("classic book: no case / final answer")
    finals = case.get("finals") or [case]
    return [f for f in finals if f.get("clues")]


@check(
    "L4.all_clues_required",
    "BLOCKER",
    "Final answer needs every clue: all clues -> 1 candidate, any clue dropped -> > 1",
)
def all_clues_required(ctx: Any) -> list[Finding]:
    out = []
    finals = _cases(ctx)
    if not finals:
        return [Finding(message="case has no declarative clues for the final answer")]
    for f in finals:
        rep = check_case(f)
        for p in rep.problems():
            out.append(
                Finding(
                    message=f"{f.get('kind', 'final')}: {p}",
                    evidence={"survivors_without": rep.dropped, "solutions": rep.solutions[:10]},
                )
            )
    return out


@check(
    "L4.vault_page",
    "MAJOR",
    "Last content page = Case Vault page: domain + /solve/<book_id> printed, QR encodes that URL",
)
def vault_page(ctx: Any) -> list[Finding]:
    from forge.qa.l2 import layout, pdf
    from forge.vault.page import QR_FILE, TITLE
    from forge.vault.qr import qr_svg

    if "case_vault" not in ctx.manifest["spec"].get("back_matter", []):
        raise Skip("book has no case_vault page")
    pages = layout(ctx)["pages"]
    content = [i for i, p in enumerate(pages) if p.get("kind") != "blank"]
    last = content[-1] if content else -1
    if last < 0 or pages[last].get("title") != TITLE:
        return [Finding(message="the Case Vault page is not the last content page")]
    blocks = pages[last]["blocks"]
    img = next((b for b in blocks if b.get("kind") == "image" and b.get("url")), None)
    base_id = str(ctx.manifest.get("base_book_id", ctx.book_id))
    out = []
    if img is None or not str(img["url"]).endswith(f"/solve/{base_id}"):
        out.append(Finding(message=f"QR URL does not open /solve/{base_id}", evidence={"img": img}))
    else:
        qr = ctx.out_dir / "build" / QR_FILE
        if not qr.is_file() or qr.read_text(encoding="utf-8") != qr_svg(img["url"]):
            out.append(Finding(message="QR image missing or does not encode the page URL"))
    printed = " ".join(pdf(ctx).pages[last].text.split())
    for b in blocks:
        if b.get("kind") == "url" and b["text"] not in printed.replace(" ", ""):
            out.append(Finding(message=f"{b['text']!r} not printed on page {last + 1}"))
    if "Submit your final answer at" not in printed:
        out.append(Finding(message="'Submit your final answer at' sentence missing"))
    return out
