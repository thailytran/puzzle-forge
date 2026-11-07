"""Case Vault business logic: book registry, answer + proof checks, binding, rewards, outbox.
Every decision is stored before any e-mail goes out, so a provider failure never loses a reward."""

from __future__ import annotations

import contextlib
import csv
import io
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import Engine, and_, func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from casevault import bookcode
from casevault import db as T
from casevault.answers import KINDS, answer_hash, code_hash
from casevault.config import Settings
from casevault.providers import OrderLookup, ProviderError, Providers, new_unique_id
from casevault.security import sign

PLACES = ("etsy", "shopify", "in_person", "gift", "other")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
Status = Literal["invalid", "rate_limited", "wrong", "pending", "approved", "rejected", "duplicate"]


def norm_email(e: str) -> str:
    return e.strip().lower()


def answer_fields(answer_type: str) -> list[str]:
    return list(KINDS) if answer_type == "both" else [answer_type]


@dataclass
class Submission:
    book_id: str
    answers: dict[str, str]
    purchase_place: str
    proof: str
    email: str
    country: str
    newsletter: bool
    terms: bool
    captcha_token: str = ""
    ip: str = ""
    name: str = ""
    coupon_platform: str = ""  # "" = default from the purchase place


@dataclass
class Outcome:
    status: Status
    message: str
    errors: dict[str, str] = field(default_factory=dict)
    solve_id: int | None = None
    reward: dict[str, Any] | None = None


class Vault:
    def __init__(self, settings: Settings, engine: Engine, providers: Providers) -> None:
        self.s, self.e, self.p = settings, engine, providers
        self.rules = settings.rules

    # ------------------------------------------------------------------ books (admin API)
    def register_book(self, data: dict[str, Any]) -> dict[str, Any]:
        bid = str(data["book_id"])
        if data.get("answer_type") not in ("culprit_name", "unlock_code", "both"):
            raise ValueError("answer_type must be culprit_name | unlock_code | both")
        answers: dict[str, list[str]] = data.get("answers") or {}
        for kind in answer_fields(data["answer_type"]):
            if not answers.get(kind):
                raise ValueError(f"no answer hashes for {kind}")
        row = {
            "sku": data.get("sku", ""),
            "title": data["title"],
            "editions": data.get("editions", []),
            "answer_type": data["answer_type"],
            "cover_png_b64": data.get("cover_png_b64", ""),
            "etsy_listing_ids": [str(x) for x in data.get("etsy_listing_ids", [])],
            "shopify_product_ids": [str(x) for x in data.get("shopify_product_ids", [])],
            "active": bool(data.get("active", True)),
            "updated_at": T.now(),
        }
        with self.e.begin() as c:
            if c.execute(select(T.books.c.book_id).where(T.books.c.book_id == bid)).first():
                c.execute(update(T.books).where(T.books.c.book_id == bid).values(**row))
            else:
                c.execute(insert(T.books).values(book_id=bid, **row))
            c.execute(T.book_answers.delete().where(T.book_answers.c.book_id == bid))
            for kind, hashes in answers.items():
                for h in sorted(set(hashes)):
                    c.execute(insert(T.book_answers).values(book_id=bid, kind=kind, hash=h))
            n_codes = 0
            for batch in data.get("book_code_batches", []):
                for h in batch.get("code_hashes", []):
                    exists = c.execute(
                        select(T.book_codes.c.hash).where(T.book_codes.c.hash == h)
                    ).first()
                    if not exists:
                        c.execute(
                            insert(T.book_codes).values(
                                hash=h,
                                book_id=bid,
                                batch_id=batch["batch_id"],
                                channel=batch.get("channel", "print"),
                            )
                        )
                        n_codes += 1
        return {"book_id": bid, "new_codes": n_codes, "url": f"{self.s.public_url}/solve/{bid}"}

    def book(self, book_id: str) -> dict[str, Any] | None:
        with self.e.connect() as c:
            r = c.execute(select(T.books).where(T.books.c.book_id == book_id)).mappings().first()
        return dict(r) if r else None

    def books(self, active_only: bool = True) -> list[dict[str, Any]]:
        q = select(T.books).order_by(T.books.c.title)
        if active_only:
            q = q.where(T.books.c.active.is_(True))
        with self.e.connect() as c:
            return [dict(r) for r in c.execute(q).mappings()]

    # ------------------------------------------------------------------ rate limits
    def _hits(self, c: Connection, key: str, minutes: int) -> int:
        since = T.now() - timedelta(minutes=minutes)
        q = select(func.count()).where(and_(T.attempts.c.key == key, T.attempts.c.at >= since))
        return int(c.execute(q).scalar_one())

    def _hit(self, c: Connection, key: str) -> None:
        c.execute(insert(T.attempts).values(key=key))

    def _fraud(self, c: Connection, kind: str, email: str, ip: str, **detail: Any) -> None:
        c.execute(insert(T.fraud_log).values(kind=kind, email=email, ip=ip, detail=detail))

    # ------------------------------------------------------------------ validation
    def _validate(self, sub: Submission, book: dict[str, Any] | None) -> dict[str, str]:
        err: dict[str, str] = {}
        if not book or not book["active"]:
            return {"book_id": "Unknown book."}
        for kind in answer_fields(book["answer_type"]):
            if not sub.answers.get(kind, "").strip():
                err[kind] = "Enter your final answer."
        if sub.purchase_place not in PLACES:
            err["purchase_place"] = "Choose where you bought the book."
        proof = sub.proof.strip()
        if sub.purchase_place == "etsy" and not proof:
            err["proof"] = "Your Etsy order number is required."
        elif sub.purchase_place == "shopify" and not proof:
            err["proof"] = "Enter the Book Code from your PDF or your order number."
        elif sub.purchase_place in ("in_person", "gift", "other"):
            if not proof:
                err["proof"] = "Enter the Book Code printed in your book."
            elif not bookcode.is_valid(proof):
                err["proof"] = "This Book Code is not valid. Check for typos."
        if not EMAIL_RE.match(norm_email(sub.email)):
            err["email"] = "Enter a valid e-mail address."
        if not re.fullmatch(r"[A-Za-z]{2}", sub.country.strip()):
            err["country"] = "Choose your country."
        elif not sub.newsletter and self.s.newsletter_required(sub.country):
            err["newsletter"] = "Please tick the newsletter box to receive your reward."
        if not sub.terms:
            err["terms"] = "Please accept the Terms and Privacy Policy."
        if sub.coupon_platform not in ("", "etsy", "shopify"):
            err["coupon_platform"] = "Choose Etsy or Shopify."
        if not err and not self.p.captcha.verify(sub.captcha_token, sub.ip):
            err["captcha"] = "Captcha check failed. Please try again."
        return err

    # ------------------------------------------------------------------ proofs
    def _proof_key(self, sub: Submission, book_id: str) -> tuple[str, str]:
        raw = sub.proof.strip()
        if sub.purchase_place == "etsy":
            return "etsy_order", re.sub(r"[^0-9A-Za-z]", "", raw)
        if sub.purchase_place == "shopify" and not bookcode.is_valid(raw):
            return "shopify_order", re.sub(r"[^0-9A-Za-z]", "", raw)
        return "book_code", code_hash(self.s.answer_key, book_id, bookcode.canonical(raw))

    def _match(self, book: dict[str, Any], lines: list[dict[str, str]], kind: str) -> bool:
        ids = set(book["etsy_listing_ids" if kind == "etsy" else "shopify_product_ids"])
        title = book["title"].casefold()
        for ln in lines:
            if ln.get("listing_id") in ids or ln.get("product_id") in ids:
                return True
            if book["sku"] and ln.get("sku") == book["sku"]:
                return True
            if title and title in ln.get("title", "").casefold():
                return True
        return False

    def _verdict(
        self, c: Connection, kind: str, value: str, book: dict[str, Any]
    ) -> tuple[str, str]:
        """-> ("ok" | "pending" | "rejected", reason)."""
        if kind == "book_code":
            row = c.execute(
                select(T.book_codes.c.book_id).where(T.book_codes.c.hash == value)
            ).first()
            if not row or row[0] != book["book_id"]:
                return "rejected", "This Book Code does not belong to this book."
            return "ok", ""
        if kind == "etsy_order":
            rows = c.execute(
                select(T.etsy_orders).where(T.etsy_orders.c.order_id == value)
            ).mappings()
            lines = [dict(r) for r in rows]
            if not lines:
                look = self.p.etsy.lookup(value)
                if look.status == "found":
                    for ln in look.lines:
                        self._store_etsy_line(c, value, ln, "api")
                    lines = look.lines
                elif look.status == "not_found":
                    return "rejected", "We could not find this order in our Etsy shop."
                else:
                    return "pending", "Etsy order not in our records yet."
            if self._match(book, lines, "etsy"):
                return "ok", ""
            return "rejected", "This Etsy order does not contain this book."
        look2: OrderLookup = self.p.shopify.find_order(value)
        if look2.status == "found":
            if self._match(book, look2.lines, "shopify"):
                return "ok", ""
            return "rejected", "This Shopify order does not contain this book."
        if look2.status == "not_found":
            return "rejected", "We could not find this Shopify order."
        return "pending", "Shopify order could not be checked yet."

    def _store_etsy_line(self, c: Connection, order: str, ln: dict[str, str], src: str) -> bool:
        vals = {
            "order_id": order,
            "listing_id": str(ln.get("listing_id", "")),
            "title": str(ln.get("title", ""))[:300],
            "sku": str(ln.get("sku", "")),
        }
        q = select(T.etsy_orders.c.id).where(
            and_(*(getattr(T.etsy_orders.c, k) == v for k, v in vals.items()))
        )
        if c.execute(q).first():
            return False
        c.execute(insert(T.etsy_orders).values(**vals, source=src))
        return True

    def _proof_id(self, c: Connection, kind: str, value: str) -> int:
        q = select(T.proofs.c.id).where(and_(T.proofs.c.kind == kind, T.proofs.c.value == value))
        row = c.execute(q).first()
        if row:
            return int(row[0])
        return int(
            c.execute(insert(T.proofs).values(kind=kind, value=value)).inserted_primary_key[0]
        )

    # ------------------------------------------------------------------ customers & consent
    def _customer(self, c: Connection, sub: Submission, email: str) -> None:
        row = c.execute(select(T.customers).where(T.customers.c.email == email)).mappings().first()
        vals = {
            "country": sub.country.upper(),
            "purchase_place": sub.purchase_place,
            **({"name": sub.name.strip()[:120]} if sub.name.strip() else {}),
        }
        if sub.newsletter:
            vals |= {"newsletter": True, "unsubscribed_at": None}
        if row:
            c.execute(update(T.customers).where(T.customers.c.email == email).values(**vals))
        else:
            c.execute(insert(T.customers).values(email=email, **vals))
        consent = self.rules["consent"]
        c.execute(
            insert(T.consents).values(
                email=email,
                ip=sub.ip,
                country=sub.country.upper(),
                form_version=str(self.rules.get("form_version", 1)),
                newsletter=sub.newsletter,
                newsletter_text=consent["newsletter_text"],
                terms_text=consent["terms_text"],
            )
        )
        if sub.newsletter:
            self._enqueue(
                c,
                "klaviyo_subscribe",
                {
                    "email": email,
                    "at": T.now().isoformat(),
                    "source": f"{self.s.site_name} form v{self.rules.get('form_version', 1)}",
                },
            )

    # ------------------------------------------------------------------ submit
    def submit(self, sub: Submission) -> Outcome:
        book = self.book(sub.book_id)
        errors = self._validate(sub, book)
        if errors:
            return Outcome("invalid", "Please fix the highlighted fields.", errors)
        assert book is not None
        email = norm_email(sub.email)
        lim = self.rules["limits"]
        kind, value = self._proof_key(sub, book["book_id"])
        lock_key = f"wrong|{kind}|{value}|{book['book_id']}"
        lock_key_email = f"wrong|{email}|{book['book_id']}"
        with self.e.begin() as c:
            if (
                self._hits(c, f"ip|{sub.ip}", 60) >= lim["ip_per_hour"]
                or self._hits(c, f"email|{email}", 60) >= lim["email_per_hour"]
            ):
                self._fraud(c, "rate_limited", email, sub.ip, book_id=book["book_id"])
                return Outcome("rate_limited", "Too many attempts. Please try again later.")
            mins, max_wrong = lim["lockout_minutes"], lim["wrong_per_proof_book"]
            if (
                self._hits(c, lock_key, mins) >= max_wrong
                or self._hits(c, lock_key_email, mins) >= max_wrong
            ):
                self._fraud(c, "locked_out", email, sub.ip, book_id=book["book_id"])
                return Outcome(
                    "rate_limited", f"Too many wrong answers. Try again in {mins} minutes."
                )
            self._hit(c, f"ip|{sub.ip}")
            self._hit(c, f"email|{email}")
            if not self._answer_ok(c, book, sub.answers):
                self._hit(c, lock_key)
                self._hit(c, lock_key_email)
                sid = self._new_solve(c, sub, email, False, "wrong", None)
                left = max_wrong - self._hits(c, lock_key, mins)
                return Outcome(
                    "wrong",
                    f"That is not the answer. Look at every clue again ({left} tries left).",
                    solve_id=sid,
                )
            self._customer(c, sub, email)
            verdict, reason = self._verdict(c, kind, value, book)
            pid = self._proof_id(c, kind, value)
            if verdict == "rejected":
                self._hit(c, lock_key)
                sid = self._new_solve(c, sub, email, True, "rejected", pid, reason)
                return Outcome(
                    "rejected", f"Correct answer, but {reason[0].lower()}{reason[1:]}", solve_id=sid
                )
            if verdict == "pending":
                bound = self._bound_to_other(c, pid, email)
                if bound:
                    return self._reject_reuse(c, sub, email, pid)
                sid = self._new_solve(c, sub, email, True, "pending", pid, reason)
                self._event(c, "Verification Pending", email, self._book_props(book, sid))
                return Outcome(
                    "pending",
                    "Correct! We will verify your order and e-mail your reward as soon as it is "
                    "confirmed.",
                    solve_id=sid,
                )
            sid = self._new_solve(c, sub, email, True, "pending", pid)
            return self._approve(c, sid)

    def _answer_ok(self, c: Connection, book: dict[str, Any], answers: dict[str, str]) -> bool:
        for kind in answer_fields(book["answer_type"]):
            h = answer_hash(self.s.answer_key, book["book_id"], kind, answers.get(kind, ""))
            q = select(T.book_answers.c.id).where(
                and_(
                    T.book_answers.c.book_id == book["book_id"],
                    T.book_answers.c.kind == kind,
                    T.book_answers.c.hash == h,
                )
            )
            if not c.execute(q).first():
                return False
        return True

    def _new_solve(
        self,
        c: Connection,
        sub: Submission,
        email: str,
        correct: bool,
        status: str,
        pid: int | None,
        reason: str = "",
    ) -> int:
        platform = sub.coupon_platform or ("etsy" if sub.purchase_place == "etsy" else "shopify")
        res = c.execute(
            insert(T.solves).values(
                book_id=sub.book_id,
                email=email,
                correct=correct,
                status=status,
                reason=reason,
                purchase_place=sub.purchase_place,
                proof_id=pid,
                coupon_platform=platform,
                ip=sub.ip,
                decided_at=None if status == "pending" else T.now(),
            )
        )
        return int(res.inserted_primary_key[0])

    def _bound_to_other(self, c: Connection, pid: int, email: str) -> bool:
        row = c.execute(select(T.proofs.c.email).where(T.proofs.c.id == pid)).first()
        return bool(row and row[0] and row[0] != email)

    def _reject_reuse(self, c: Connection, sub: Submission, email: str, pid: int) -> Outcome:
        self._fraud(c, "proof_reuse", email, sub.ip, book_id=sub.book_id, proof_id=pid)
        sid = self._new_solve(c, sub, email, True, "rejected", pid, "proof used by another e-mail")
        return Outcome(
            "rejected",
            "This proof of purchase was already used with another e-mail address.",
            solve_id=sid,
        )

    def _set_solve(self, c: Connection, sid: int, status: str, reason: str = "") -> None:
        c.execute(
            update(T.solves)
            .where(T.solves.c.id == sid)
            .values(status=status, reason=reason, decided_at=T.now())
        )

    def _approve(self, c: Connection, sid: int, from_pending: bool = False) -> Outcome:
        s = c.execute(select(T.solves).where(T.solves.c.id == sid)).mappings().one()
        email, bid, pid = s["email"], s["book_id"], s["proof_id"]
        book = c.execute(select(T.books).where(T.books.c.book_id == bid)).mappings().one()
        if pid is not None and self._bound_to_other(c, pid, email):
            self._fraud(c, "proof_reuse", email, s["ip"], book_id=bid, proof_id=pid)
            self._set_solve(c, sid, "rejected", "proof used by another e-mail")
            return Outcome(
                "rejected",
                "This proof of purchase was already used with another e-mail address.",
                solve_id=sid,
            )
        already = c.execute(
            select(T.solves.c.id).where(
                and_(
                    T.solves.c.email == email,
                    T.solves.c.book_id == bid,
                    T.solves.c.status == "approved",
                )
            )
        ).first()
        if already:
            self._set_solve(c, sid, "duplicate", "book already solved by this e-mail")
            return Outcome(
                "duplicate",
                "Correct! You already solved this case, so it does not count twice.",
                solve_id=sid,
            )
        if pid is not None:
            try:
                with c.begin_nested():
                    c.execute(insert(T.redemptions).values(proof_id=pid, book_id=bid, solve_id=sid))
            except IntegrityError:
                self._set_solve(c, sid, "duplicate", "proof already redeemed for this book")
                return Outcome(
                    "duplicate", "This proof was already redeemed for this book.", solve_id=sid
                )
            c.execute(
                update(T.proofs)
                .where(and_(T.proofs.c.id == pid, T.proofs.c.email.is_(None)))
                .values(email=email, bound_at=T.now())
            )
        self._set_solve(c, sid, "approved")
        count = self.solved_count(c, email)
        reward = self._issue_reward(c, email, sid, count, s["coupon_platform"])
        props = self._book_props(dict(book), sid)
        if from_pending:
            self._event(c, "Verification Approved", email, props)
        self._profile(c, email)
        if reward["status"] in ("issued", "choose"):
            self._event(c, "Case Solved", email, self._solved_props(dict(book), sid, count, reward))
        self._enqueue(
            c, "telegram", {"text": f"Case solved: {book['title']} by {email} (#{count})"}
        )
        return Outcome("approved", "Correct! Case solved.", solve_id=sid, reward=reward)

    # ------------------------------------------------------------------ rewards
    def solved_count(self, c: Connection, email: str) -> int:
        q = select(func.count(func.distinct(T.solves.c.book_id))).where(
            and_(T.solves.c.email == email, T.solves.c.status == "approved")
        )
        return int(c.execute(q).scalar_one())

    def tier_for(self, count: int) -> int | None:
        m = int(self.rules["rewards"]["milestone"])
        if count > m and not self.rules["rewards"].get("cycle", True):
            return None
        return (count - 1) % m + 1

    def _issue_reward(
        self, c: Connection, email: str, sid: int, count: int, platform: str
    ) -> dict[str, Any]:
        tier = self.tier_for(count)
        if tier is None:
            return {"status": "none", "tier": 0}
        m = int(self.rules["rewards"]["milestone"])
        expires = T.now() + timedelta(days=int(self.rules["rewards"]["coupon_days"]))
        if tier == m:
            vals = {"tier": tier, "percent": 100, "platform": "shopify", "status": "choose"}
        else:
            pct = int(self.rules["rewards"]["tiers"][tier])
            vals = {"tier": tier, "percent": pct, "platform": platform, "status": "code_pending"}
        rid = int(
            c.execute(
                insert(T.rewards).values(
                    email=email, solve_id=sid, solve_count=count, expires_at=expires, **vals
                )
            ).inserted_primary_key[0]
        )
        if vals["status"] == "code_pending":
            self._fill_code(c, rid)
        return self.reward(c, rid)

    def reward(self, c: Connection, rid: int) -> dict[str, Any]:
        return dict(c.execute(select(T.rewards).where(T.rewards.c.id == rid)).mappings().one())

    def _new_code(self) -> str:
        body = "".join(secrets.choice(bookcode.ALPHABET) for _ in range(8))
        return f"{self.rules['coupons']['code_prefix']}-{body}"

    def _fill_code(self, c: Connection, rid: int, product_id: str | None = None) -> bool:
        r = self.reward(c, rid)
        if r["platform"] == "etsy":
            row = (
                c.execute(
                    select(T.coupon_pool)
                    .where(
                        and_(
                            T.coupon_pool.c.percent == r["percent"],
                            T.coupon_pool.c.reward_id.is_(None),
                            (T.coupon_pool.c.expires_at.is_(None))
                            | (T.coupon_pool.c.expires_at > T.now()),
                        )
                    )
                    .order_by(T.coupon_pool.c.id)
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if not row:
                self._enqueue(
                    c, "telegram", {"text": f"Etsy coupon pool EMPTY for {r['percent']}%"}
                )
                self._enqueue(c, "coupon", {"reward_id": rid}, delay_min=60)
                return False
            c.execute(
                update(T.coupon_pool).where(T.coupon_pool.c.id == row["id"]).values(reward_id=rid)
            )
            exp = min(x for x in (row["expires_at"], r["expires_at"]) if x is not None)
            c.execute(
                update(T.rewards)
                .where(T.rewards.c.id == rid)
                .values(code=row["code"], status="issued", expires_at=exp)
            )
            left = self.pool_left(c, r["percent"])
            if left < int(self.rules["coupons"]["etsy_low_stock"]):
                self._enqueue(
                    c,
                    "telegram",
                    {"text": f"Etsy coupon pool low: {left} left for {r['percent']}%"},
                )
            return True
        code = self._new_code()
        try:
            self.p.shopify.create_discount(
                code,
                r["percent"],
                r["expires_at"],
                product_id,
                f"{self.s.site_name} reward #{rid} ({r['percent']}%)",
            )
        except ProviderError as exc:
            self._enqueue(
                c, "coupon", {"reward_id": rid, "product_id": product_id, "err": str(exc)}
            )
            return False
        c.execute(update(T.rewards).where(T.rewards.c.id == rid).values(code=code, status="issued"))
        return True

    def pool_left(self, c: Connection, percent: int) -> int:
        q = select(func.count()).where(
            and_(T.coupon_pool.c.percent == percent, T.coupon_pool.c.reward_id.is_(None))
        )
        return int(c.execute(q).scalar_one())

    def choose_gift(self, email: str, rid: int, book_id: str) -> dict[str, Any]:
        email = norm_email(email)
        with self.e.begin() as c:
            r = self.reward(c, rid)
            if r["email"] != email or r["status"] != "choose":
                raise ValueError("gift not available")
            book = c.execute(select(T.books).where(T.books.c.book_id == book_id)).mappings().first()
            if not book or not book["active"]:
                raise ValueError("unknown book")
            c.execute(update(T.rewards).where(T.rewards.c.id == rid).values(gift_book_id=book_id))
            pids = list(book["shopify_product_ids"])
            if self.rules["rewards"].get("gift") == "shopify_code" and pids:
                if self._fill_code(c, rid, product_id=pids[0]):
                    r = self.reward(c, rid)
                    props = {
                        "book_title": book["title"],
                        "coupon_code": r["code"],
                        "coupon_platform": "shopify",
                        "coupon_where": self.s.shopify_store_url,
                        "coupon_expires": r["expires_at"].date().isoformat(),
                        "account_url": self.account_link(email),
                    }
                    self._event(c, "Gift Ready", email, props)
                    return r
                return self.reward(c, rid)
            c.execute(update(T.rewards).where(T.rewards.c.id == rid).values(status="requested"))
            self._enqueue(c, "telegram", {"text": f"Gift request: {email} chose {book['title']}"})
            return self.reward(c, rid)

    # ------------------------------------------------------------------ events
    def _enqueue(
        self, c: Connection, kind: str, payload: dict[str, Any], delay_min: int = 0
    ) -> None:
        c.execute(
            insert(T.outbox).values(
                kind=kind, payload=payload, next_at=T.now() + timedelta(minutes=delay_min)
            )
        )

    def _event(self, c: Connection, name: str, email: str, props: dict[str, Any]) -> None:
        self._enqueue(
            c,
            "klaviyo_event",
            {"name": name, "email": email, "props": props, "uid": new_unique_id()},
        )

    def _profile(self, c: Connection, email: str) -> None:
        cu = c.execute(select(T.customers).where(T.customers.c.email == email)).mappings().first()
        if not cu:
            return
        rows = c.execute(
            select(T.solves.c.book_id)
            .where(and_(T.solves.c.email == email, T.solves.c.status == "approved"))
            .distinct()
        ).all()
        count = len(rows)
        attrs = {
            "first_name": cu["name"],
            "country": cu["country"],
            "purchase_place": cu["purchase_place"],
            "cases_solved": count,
            "books_solved": sorted(r[0] for r in rows),
            "current_tier": self.tier_for(count) if count else 0,
        }
        self._enqueue(c, "klaviyo_profile", {"email": email, "attrs": attrs})

    def _book_props(self, book: dict[str, Any], sid: int) -> dict[str, Any]:
        return {
            "book_title": book["title"],
            "sku": book["sku"],
            "book_id": book["book_id"],
            "solve_id": sid,
        }

    def certificate_url(self, sid: int) -> str:
        tok = sign(self.s.secret_key, {"sid": sid}, 3600 * 24 * 365 * 5, "cert")
        return f"{self.s.public_url}/certificate/{sid}.pdf?t={tok}"

    def account_link(self, email: str) -> str:
        mins = int(self.rules.get("login_link_minutes", 30))
        tok = sign(self.s.secret_key, {"email": email}, mins * 60, "login")
        return f"{self.s.public_url}/account?t={tok}"

    def progress_text(self, count: int) -> tuple[str, int]:
        m = int(self.rules["rewards"]["milestone"])
        k = (count - 1) % m + 1
        if k == m:
            return f"{m}/{m} cases solved – your FREE book is waiting!", 0
        return f"{k}/{m} cases solved – {m - k} more to earn a FREE book", m - k

    def _solved_props(
        self, book: dict[str, Any], sid: int, count: int, r: dict[str, Any]
    ) -> dict[str, Any]:
        text, left = self.progress_text(count)
        where = self.s.etsy_shop_url if r["platform"] == "etsy" else self.s.shopify_store_url
        return {
            **self._book_props(book, sid),
            "solve_count": count,
            "reward_tier": r["tier"],
            "reward_percent": r["percent"],
            "is_gift": r["status"] == "choose",
            "coupon_code": r["code"],
            "coupon_platform": r["platform"],
            "coupon_where": where,
            "coupon_expires": r["expires_at"].date().isoformat() if r["expires_at"] else "",
            "certificate_url": self.certificate_url(sid),
            "next_milestone": left,
            "progress_text": text,
            "account_url": self.account_link(r["email"]),
        }

    # ------------------------------------------------------------------ outbox worker
    def process_outbox(self, limit: int = 100) -> dict[str, int]:
        done = failed = 0
        with self.e.connect() as c:
            jobs = (
                c.execute(
                    select(T.outbox)
                    .where(and_(T.outbox.c.status == "queued", T.outbox.c.next_at <= T.now()))
                    .order_by(T.outbox.c.id)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
        for job in jobs:
            try:
                with self.e.begin() as c:
                    self._run_job(c, dict(job))
                    c.execute(
                        update(T.outbox).where(T.outbox.c.id == job["id"]).values(status="done")
                    )
                done += 1
            except Exception as exc:  # retried with back-off; alert after 3 failures
                failed += 1
                n = job["attempts"] + 1
                with self.e.begin() as c:
                    c.execute(
                        update(T.outbox)
                        .where(T.outbox.c.id == job["id"])
                        .values(
                            attempts=n,
                            last_error=str(exc)[:500],
                            status="dead" if n >= 20 else "queued",
                            next_at=T.now() + timedelta(minutes=min(2**n, 360)),
                        )
                    )
                if n == 3 and job["kind"] != "telegram":
                    with contextlib.suppress(Exception):  # alerting is best effort
                        self.p.telegram.send(f"Case Vault: {job['kind']} failing ({exc})"[:300])
        return {"done": done, "failed": failed}

    def _run_job(self, c: Connection, job: dict[str, Any]) -> None:
        p, k = job["payload"], job["kind"]
        if k == "klaviyo_event":
            self.p.klaviyo.event(p["name"], p["email"], p["props"], p["uid"])
        elif k == "klaviyo_profile":
            self.p.klaviyo.upsert_profile(p["email"], p["attrs"])
        elif k == "klaviyo_subscribe":
            self.p.klaviyo.subscribe(p["email"], datetime.fromisoformat(p["at"]), p["source"])
        elif k == "klaviyo_unsubscribe":
            self.p.klaviyo.unsubscribe(p["email"])
        elif k == "telegram":
            self.p.telegram.send(p["text"])
        elif k == "coupon":
            r = self.reward(c, p["reward_id"])
            if r["status"] in ("code_pending", "choose"):
                if not self._fill_code(c, r["id"], p.get("product_id")):
                    raise ProviderError("coupon still not available")
                self._after_late_code(c, r["id"])
        else:
            raise ValueError(f"unknown job {k}")

    def _after_late_code(self, c: Connection, rid: int) -> None:
        r = self.reward(c, rid)
        s = c.execute(select(T.solves).where(T.solves.c.id == r["solve_id"])).mappings().one()
        book = c.execute(select(T.books).where(T.books.c.book_id == s["book_id"])).mappings().one()
        self._event(
            c,
            "Case Solved",
            r["email"],
            self._solved_props(dict(book), s["id"], r["solve_count"], r),
        )

    # ------------------------------------------------------------------ pending re-check
    def recheck_pending(self) -> dict[str, int]:
        out = {"approved": 0, "rejected": 0, "still_pending": 0}
        days = int(self.rules["limits"]["pending_days"])
        with self.e.connect() as c:
            ids = [
                r[0]
                for r in c.execute(
                    select(T.solves.c.id)
                    .where(T.solves.c.status == "pending")
                    .order_by(T.solves.c.id)
                )
            ]
        for sid in ids:
            with self.e.begin() as c:
                s = c.execute(select(T.solves).where(T.solves.c.id == sid)).mappings().one()
                pr = (
                    c.execute(select(T.proofs).where(T.proofs.c.id == s["proof_id"]))
                    .mappings()
                    .one()
                )
                book = (
                    c.execute(select(T.books).where(T.books.c.book_id == s["book_id"]))
                    .mappings()
                    .one()
                )
                verdict, reason = self._verdict(c, pr["kind"], pr["value"], dict(book))
                if verdict == "pending" and s["at"] < T.now() - timedelta(days=days):
                    verdict, reason = "rejected", "order could not be verified in time"
                if verdict == "ok":
                    res = self._approve(c, sid, from_pending=True)
                    out["approved" if res.status == "approved" else "rejected"] += 1
                elif verdict == "rejected":
                    self._set_solve(c, sid, "rejected", reason)
                    self._event(
                        c,
                        "Verification Rejected",
                        s["email"],
                        {**self._book_props(dict(book), sid), "reason": reason},
                    )
                    out["rejected"] += 1
                else:
                    out["still_pending"] += 1
        return out

    def decide_pending(self, sid: int, approve: bool, note: str = "") -> Outcome:
        """Owner decision on the admin page (manual verification)."""
        with self.e.begin() as c:
            s = c.execute(select(T.solves).where(T.solves.c.id == sid)).mappings().one()
            if s["status"] != "pending":
                raise ValueError("solve is not pending")
            if approve:
                return self._approve(c, sid, from_pending=True)
            self._set_solve(c, sid, "rejected", note or "rejected by admin")
            book = (
                c.execute(select(T.books).where(T.books.c.book_id == s["book_id"])).mappings().one()
            )
            self._event(
                c,
                "Verification Rejected",
                s["email"],
                {**self._book_props(dict(book), sid), "reason": note},
            )
            return Outcome("rejected", "rejected", solve_id=sid)

    # ------------------------------------------------------------------ imports
    @staticmethod
    def _col(row: dict[str, str], *names: str) -> str:
        low = {k.strip().casefold(): v for k, v in row.items() if k}
        for n in names:
            if n.casefold() in low and low[n.casefold()] is not None:
                return str(low[n.casefold()]).strip()
        return ""

    def import_etsy_csv(self, text: str) -> dict[str, int]:
        """Etsy Shop Manager → Settings → Options → Download data → Orders / Order Items CSV."""
        added = 0
        with self.e.begin() as c:
            for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
                order = re.sub(
                    r"[^0-9A-Za-z]",
                    "",
                    self._col(row, "Order ID", "Order Id", "Receipt ID", "order_id"),
                )
                if not order:
                    continue
                ln = {
                    "listing_id": self._col(row, "Listing ID", "Listing Id", "listing_id"),
                    "title": self._col(row, "Item Name", "Title", "Item Title"),
                    "sku": self._col(row, "SKU", "Sku"),
                }
                added += self._store_etsy_line(c, order, ln, "csv")
        return {"lines_added": added, **self.recheck_pending()}

    def import_pool_csv(self, text: str) -> int:
        """CSV columns: percent (or tier 10/20/30/40), code, expires (YYYY-MM-DD, optional)."""
        n = 0
        with self.e.begin() as c:
            for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
                code = self._col(row, "code", "coupon", "coupon code")
                pct = self._col(row, "percent", "tier", "discount")
                if not code or not pct:
                    continue
                exp = self._col(row, "expires", "expiry", "end date")
                try:
                    with c.begin_nested():
                        c.execute(
                            insert(T.coupon_pool).values(
                                platform="etsy",
                                percent=int(re.sub(r"\D", "", pct)),
                                code=code,
                                expires_at=datetime.fromisoformat(exp) if exp else None,
                            )
                        )
                    n += 1
                except IntegrityError:
                    continue
        self.retry_coupon_jobs()
        return n

    def retry_coupon_jobs(self) -> None:
        with self.e.begin() as c:
            c.execute(
                update(T.outbox)
                .where(and_(T.outbox.c.kind == "coupon", T.outbox.c.status == "queued"))
                .values(next_at=T.now())
            )
        self.process_outbox()

    # ------------------------------------------------------------------ account
    def account(self, email: str) -> dict[str, Any]:
        email = norm_email(email)
        with self.e.connect() as c:
            solved = (
                c.execute(
                    select(T.solves.c.book_id, T.books.c.title, T.solves.c.at, T.solves.c.id)
                    .join(T.books, T.books.c.book_id == T.solves.c.book_id)
                    .where(and_(T.solves.c.email == email, T.solves.c.status == "approved"))
                    .order_by(T.solves.c.at)
                )
                .mappings()
                .all()
            )
            pending = c.execute(
                select(func.count()).where(
                    and_(T.solves.c.email == email, T.solves.c.status == "pending")
                )
            ).scalar_one()
            rewards = (
                c.execute(
                    select(T.rewards).where(T.rewards.c.email == email).order_by(T.rewards.c.id)
                )
                .mappings()
                .all()
            )
            cu = (
                c.execute(select(T.customers).where(T.customers.c.email == email))
                .mappings()
                .first()
            )
        count = len({r["book_id"] for r in solved})
        text, left = self.progress_text(count) if count else ("0/5 cases solved", 5)
        return {
            "email": email,
            "customer": dict(cu) if cu else None,
            "solved": [dict(r) for r in solved],
            "pending": int(pending),
            "rewards": [dict(r) for r in rewards],
            "count": count,
            "progress_text": text,
            "next_milestone": left,
        }

    def unsubscribe(self, email: str) -> None:
        """Newsletter only: coupons already earned stay valid, reward e-mails keep coming."""
        email = norm_email(email)
        with self.e.begin() as c:
            c.execute(
                update(T.customers)
                .where(T.customers.c.email == email)
                .values(newsletter=False, unsubscribed_at=T.now())
            )
            self._enqueue(c, "klaviyo_unsubscribe", {"email": email})

    # ------------------------------------------------------------------ admin data
    def stats(self) -> list[dict[str, Any]]:
        with self.e.connect() as c:
            rows = (
                c.execute(
                    select(
                        T.books.c.book_id,
                        T.books.c.title,
                        T.books.c.sku,
                        func.sum(T.solves.c.correct.cast(T.Integer)).label("correct"),
                        func.count(T.solves.c.id).label("total"),
                    )
                    .select_from(
                        T.books.outerjoin(T.solves, T.solves.c.book_id == T.books.c.book_id)
                    )
                    .group_by(T.books.c.book_id, T.books.c.title, T.books.c.sku)
                    .order_by(T.books.c.title)
                )
                .mappings()
                .all()
            )
        out = []
        for r in rows:
            total, ok = int(r["total"] or 0), int(r["correct"] or 0)
            out.append(
                {
                    **dict(r),
                    "correct": ok,
                    "wrong": total - ok,
                    "rate": round(100 * ok / total) if total else 0,
                }
            )
        return out

    def consenting_emails(self) -> list[dict[str, Any]]:
        with self.e.connect() as c:
            rows = (
                c.execute(
                    select(T.customers)
                    .where(
                        and_(
                            T.customers.c.newsletter.is_(True),
                            T.customers.c.unsubscribed_at.is_(None),
                        )
                    )
                    .order_by(T.customers.c.email)
                )
                .mappings()
                .all()
            )
            out = []
            for r in rows:
                last = (
                    c.execute(
                        select(T.consents)
                        .where(
                            and_(
                                T.consents.c.email == r["email"], T.consents.c.newsletter.is_(True)
                            )
                        )
                        .order_by(T.consents.c.id.desc())
                        .limit(1)
                    )
                    .mappings()
                    .first()
                )
                out.append(
                    {
                        "email": r["email"],
                        "name": r["name"],
                        "country": r["country"],
                        "consented_at": last["at"].isoformat() if last else "",
                        "ip": last["ip"] if last else "",
                        "form_version": last["form_version"] if last else "",
                    }
                )
        return out
