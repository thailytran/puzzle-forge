"""The `case_vault` last page: "Submit your final answer at <DOMAIN> to unlock rewards" + QR."""

from __future__ import annotations

from forge.layout.document import LAST_PAGE_TITLE, Page
from forge.vault.qr import qr_svg, solve_url

TITLE = LAST_PAGE_TITLE
QR_FILE = "vault/qr.svg"


def site_of(domain: str) -> str:
    return domain.removeprefix("https://").removeprefix("http://").rstrip("/")


def case_vault_page(book_id: str, domain: str = "") -> tuple[Page, dict[str, bytes]]:
    if not domain:
        from forge.config import get_settings

        domain = get_settings().vault_domain
    if not domain:
        raise ValueError("back matter 'case_vault' needs VAULT_DOMAIN in .env")
    url = solve_url(domain, book_id)
    site = site_of(domain)
    blocks = [
        {"kind": "paragraph", "text": "Solved the case? Submit your final answer at"},
        {"kind": "url", "text": site},
        {
            "kind": "paragraph",
            "text": "to unlock rewards: a discount on your next case, and a "
            "free new book when you have solved five.",
        },
        {"kind": "spacer", "height_in": 0.2},
        {"kind": "image", "path": QR_FILE, "width_in": 1.9, "url": url},
        {"kind": "url", "text": f"{site}/solve/{book_id}"},
        {"kind": "spacer", "height_in": 0.2},
        {
            "kind": "paragraph",
            "text": "Scan the code with your phone camera to open this book's "
            "page. Keep your order number or the Book Code from your "
            "copy ready. The full solutions are printed at the back of "
            "this book; the website is an extra for rewards.",
        },
    ]
    return Page(kind="text", title=TITLE, blocks=blocks), {QR_FILE: qr_svg(url).encode()}
