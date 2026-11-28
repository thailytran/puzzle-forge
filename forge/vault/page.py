"""The `case_vault` last page: "Submit your final answer at <DOMAIN> to unlock rewards" + QR."""

from __future__ import annotations

from forge.layout.document import LAST_PAGE_TITLE, Page
from forge.vault.qr import qr_svg, solve_url

TITLE = LAST_PAGE_TITLE
QR_FILE = "vault/qr.svg"

# Mirrors DEFAULT_RULES in apps/casevault_cf/src/10_db.js (the owner may change them in /admin).
POINT_ROWS = [
    "Create your free account: 20 points",
    "Solve a case (verified purchase): 100 points, +30 if you were right on the first try",
    "Finish a whole series: +200 points",
    "A friend you invite buys and solves their first case: 100 points",
    "Your birthday month: 50 points",
]
RANK_LINE = (
    "Ranks: Rookie (start), Detective (300 points), Inspector (800 points), "
    "Chief Inspector (1,500 points)."
)
REWARD_ROWS = [
    "Every solved case: 15% off your next book, valid for 90 days",
    "Inspector and above: spend 1,200 points on a book of your choice",
    "Detectives get new-case e-mails 48 hours early",
]


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
        {"kind": "spacer", "height_in": 0.35},
        {"kind": "paragraph", "text": "Solved the case? Submit your final answer at"},
        {"kind": "url", "text": site},
        {
            "kind": "paragraph",
            "text": "Everyone can read the extended ending. Create a free detective "
            "account to collect Case Points, rank up and unlock rewards.",
        },
        {"kind": "list", "items": POINT_ROWS},
        {"kind": "paragraph", "text": RANK_LINE},
        {"kind": "list", "items": REWARD_ROWS},
        {"kind": "spacer", "height_in": 0.1},
        {"kind": "image", "path": QR_FILE, "width_in": 1.5, "url": url},
        {"kind": "url", "text": f"{site}/solve/{book_id}"},
        {
            "kind": "paragraph",
            "text": "Scan the code to open this book's page. Keep your order number "
            "or the Book Code from your copy ready. The full solutions are printed "
            "at the back of this book; the website is an extra for rewards.",
        },
    ]
    return Page(kind="text", title=TITLE, blocks=blocks), {QR_FILE: qr_svg(url).encode()}
