"""Tables (SQLAlchemy Core). Prefix cv_ so they can move into the HALOSPARK Suite DB unchanged
(docs/INTEGRATION_HALOSPARK.md §7). SQLite in dev/tests, Postgres (pg8000) in production."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
)

md = MetaData()


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _id() -> Column[int]:
    return Column("id", Integer, primary_key=True, autoincrement=True)


books = Table(
    "cv_books",
    md,
    Column("book_id", String(120), primary_key=True),
    Column("sku", String(80), nullable=False, default=""),
    Column("title", String(300), nullable=False),
    Column("editions", JSON, nullable=False, default=list),
    Column("answer_type", String(20), nullable=False),
    Column("cover_png_b64", Text, nullable=False, default=""),
    Column("etsy_listing_ids", JSON, nullable=False, default=list),
    Column("shopify_product_ids", JSON, nullable=False, default=list),
    Column("active", Boolean, nullable=False, default=True),
    Column("digital_gift", Boolean, nullable=False, default=True),
    Column("registered_at", DateTime, nullable=False, default=now),
    Column("updated_at", DateTime, nullable=False, default=now),
)

book_answers = Table(
    "cv_book_answers",
    md,
    _id(),
    Column("book_id", String(120), ForeignKey("cv_books.book_id"), nullable=False, index=True),
    Column("kind", String(20), nullable=False),
    Column("hash", String(64), nullable=False),
    UniqueConstraint("book_id", "kind", "hash"),
)

book_codes = Table(
    "cv_book_codes",
    md,
    Column("hash", String(64), primary_key=True),
    Column("book_id", String(120), ForeignKey("cv_books.book_id"), nullable=False, index=True),
    Column("batch_id", String(80), nullable=False),
    Column("channel", String(30), nullable=False),
)

customers = Table(
    "cv_customers",
    md,
    Column("email", String(254), primary_key=True),
    Column("name", String(120), nullable=False, default=""),
    Column("country", String(2), nullable=False, default=""),
    Column("purchase_place", String(20), nullable=False, default=""),
    Column("newsletter", Boolean, nullable=False, default=False),
    Column("unsubscribed_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False, default=now),
)

consents = Table(  # append-only proof of consent
    "cv_consents",
    md,
    _id(),
    Column("email", String(254), nullable=False, index=True),
    Column("at", DateTime, nullable=False, default=now),
    Column("ip", String(64), nullable=False, default=""),
    Column("country", String(2), nullable=False, default=""),
    Column("form_version", String(20), nullable=False),
    Column("newsletter", Boolean, nullable=False),
    Column("newsletter_text", Text, nullable=False),
    Column("terms_text", Text, nullable=False),
)

proofs = Table(  # a proof of purchase, bound to the first e-mail that redeems it successfully
    "cv_proofs",
    md,
    _id(),
    Column("kind", String(20), nullable=False),  # etsy_order | shopify_order | book_code
    Column("value", String(120), nullable=False),  # order number, or HMAC of a Book Code
    Column("email", String(254), nullable=True),
    Column("bound_at", DateTime, nullable=True),
    UniqueConstraint("kind", "value"),
)

solves = Table(
    "cv_solves",
    md,
    _id(),
    Column("book_id", String(120), ForeignKey("cv_books.book_id"), nullable=False, index=True),
    Column("email", String(254), nullable=False, index=True),
    Column("correct", Boolean, nullable=False),
    # wrong | pending | approved | rejected | duplicate (book already solved by this e-mail)
    Column("status", String(20), nullable=False),
    Column("reason", String(200), nullable=False, default=""),
    Column("purchase_place", String(20), nullable=False),
    Column("proof_id", Integer, ForeignKey("cv_proofs.id"), nullable=True),
    Column("coupon_platform", String(20), nullable=False, default=""),
    Column("ip", String(64), nullable=False, default=""),
    Column("at", DateTime, nullable=False, default=now),
    Column("decided_at", DateTime, nullable=True),
)

redemptions = Table(  # one per (proof, book)
    "cv_redemptions",
    md,
    _id(),
    Column("proof_id", Integer, ForeignKey("cv_proofs.id"), nullable=False),
    Column("book_id", String(120), nullable=False),
    Column("solve_id", Integer, ForeignKey("cv_solves.id"), nullable=False),
    UniqueConstraint("proof_id", "book_id"),
)

rewards = Table(
    "cv_rewards",
    md,
    _id(),
    Column("email", String(254), nullable=False, index=True),
    Column("solve_id", Integer, ForeignKey("cv_solves.id"), nullable=False, unique=True),
    Column("solve_count", Integer, nullable=False),
    Column("tier", Integer, nullable=False),  # 1..5 (5 = gift)
    Column("percent", Integer, nullable=False),  # 100 for the gift
    Column("platform", String(20), nullable=False),  # shopify | etsy | manual
    Column("code", String(80), nullable=False, default=""),
    Column("status", String(20), nullable=False),  # issued | code_pending | choose | requested
    Column("expires_at", DateTime, nullable=True),
    Column("gift_book_id", String(120), nullable=True),
    Column("created_at", DateTime, nullable=False, default=now),
)

coupon_pool = Table(  # Etsy codes created by the owner, imported from CSV
    "cv_coupon_pool",
    md,
    _id(),
    Column("platform", String(20), nullable=False, default="etsy"),
    Column("percent", Integer, nullable=False),
    Column("code", String(80), nullable=False, unique=True),
    Column("expires_at", DateTime, nullable=True),
    Column("reward_id", Integer, ForeignKey("cv_rewards.id"), nullable=True),
    Column("imported_at", DateTime, nullable=False, default=now),
)

etsy_orders = Table(  # known Etsy order lines (API or CSV)
    "cv_etsy_orders",
    md,
    _id(),
    Column("order_id", String(40), nullable=False, index=True),
    Column("listing_id", String(40), nullable=False, default=""),
    Column("title", String(300), nullable=False, default=""),
    Column("sku", String(80), nullable=False, default=""),
    Column("source", String(10), nullable=False),  # api | csv
    Column("seen_at", DateTime, nullable=False, default=now),
    UniqueConstraint("order_id", "listing_id", "title"),
)

outbox = Table(  # Klaviyo / Telegram / coupon jobs with retry
    "cv_outbox",
    md,
    _id(),
    Column("kind", String(30), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("status", String(10), nullable=False, default="queued"),  # queued | done | dead
    Column("attempts", Integer, nullable=False, default=0),
    Column("next_at", DateTime, nullable=False, default=now),
    Column("last_error", Text, nullable=False, default=""),
    Column("created_at", DateTime, nullable=False, default=now),
)

fraud_log = Table(
    "cv_fraud_log",
    md,
    _id(),
    Column("at", DateTime, nullable=False, default=now),
    Column("kind", String(40), nullable=False),
    Column("email", String(254), nullable=False, default=""),
    Column("ip", String(64), nullable=False, default=""),
    Column("detail", JSON, nullable=False, default=dict),
)

attempts = Table(  # rate limiting
    "cv_attempts",
    md,
    _id(),
    Column("key", String(300), nullable=False, index=True),
    Column("at", DateTime, nullable=False, default=now),
)

admins = Table(
    "cv_admins",
    md,
    Column("username", String(60), primary_key=True),
    Column("password_hash", String(300), nullable=False),
    Column("totp_secret", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False, default=now),
)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("postgresql://"):
        url = "postgresql+pg8000://" + url.removeprefix("postgresql://")
    eng = create_engine(url, future=True)
    md.create_all(eng)
    return eng
