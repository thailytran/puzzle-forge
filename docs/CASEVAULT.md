# CASE VAULT — answers, proof of purchase, rewards (owner rules 2026-11-07, ROADMAP P9)

Case Vault (working name, owner to confirm) is the public website where a reader of an escape /
mystery / adventure book submits the final answer and unlocks rewards. Books always print their full
solutions; the website is an extra. Code: `apps/casevault/` (FastAPI + Jinja/HTMX, SQLAlchemy;
Postgres in production via `pg8000` (BSD), SQLite in dev/tests; Docker). It never imports `forge`:
Puzzle Forge talks to it only through the admin HTTP API (ports & adapters).

## 1. Flow overview

```
forge review --approve ─► vault outbox (SQLite, retry) ─► POST /api/admin/books (Bearer token)
                                                             │
reader: QR on the last page ─► /solve/<book_id> form ─► answer check (HMAC) ─► proof check ─►
  solve recorded ─► reward tier ─► coupon (Shopify API / Etsy pool) ─► Klaviyo events (outbox, retry)
                └─► Etsy order not in data yet → PENDING → re-checked on API poll / CSV import
```

## 2. Book registration (Puzzle Forge side, `forge/vault`)

When a book reaches **APPROVED** (`forge review --approve`), the pipeline enqueues a registration and
tries to send it at once; offline → it stays queued with exponential back-off.
`forge vault sync` retries the queue, `forge vault status` shows it.

Registration needs `output/<book_id>/vault.yaml` (written by the mystery pipeline, or by hand / `forge
vault init`); classic books without it are skipped (nothing to solve).

```yaml
answer_type: culprit_name          # culprit_name | unlock_code | both
culprit_name: ["Captain Reed", "Reed", "Elias Reed"]   # accepted variants
unlock_code: ["4729"]              # numeric codes: must match exactly
etsy_listing_ids: [1234567890]
shopify_product_ids: ["gid://shopify/Product/111"]
editions: [kdp, digital-8_5x11, spiral-8_5x11-color-duplex]
```

Payload `POST {VAULT_URL}/api/admin/books` (`Authorization: Bearer VAULT_ADMIN_TOKEN`), idempotent
upsert by `book_id`:

| field | content |
|---|---|
| `book_id`, `sku`, `title`, `editions` | from manifest / SKU / editions folder |
| `cover_png_b64` | page 1 thumbnail (cover.pdf once P4.2 exists) |
| `answer_type` | `culprit_name` / `unlock_code` / `both` |
| `answers` | `{kind: [hmac, …]}` — **no plaintext**: `HMAC-SHA256(VAULT_ANSWER_KEY, "<book_id>|<kind>|<normalised>")` |
| `book_code_batches` | `[{batch_id, channel: print|shopify_digital, code_hashes: [...]}]` |
| `etsy_listing_ids`, `shopify_product_ids` | matching listings / products |

**Answer matching** (identical in `forge/vault/answers.py` and `casevault/answers.py`, tested against
the same vectors): Unicode NFKD, accents removed, case-insensitive, all whitespace and punctuation
removed; every declared variant is hashed. `unlock_code`: whitespace and `-` removed, otherwise exact
(no fuzzy match, leading zeros count).

## 3. Proof of purchase (mandatory for any reward)

| Purchase place | Proof | Verification |
|---|---|---|
| **Etsy** | Etsy order (receipt) number — **required** | (a) Etsy Open API v3 `getShopReceipt` (scope `transactions_r`): receipt exists, belongs to `ETSY_SHOP_ID`, has a transaction whose `listing_id` is one of the book's listings; (b) fallback: Etsy Shop Manager **orders CSV** import (admin page / `python -m casevault import-etsy file.csv`), match order number + listing id / title |
| **Shopify** | Book Code **or** Shopify order number | Book Code: checksum + registered batch; order: Shopify Admin GraphQL `orders(query:"name:#1001")` → order of the shop, contains one of the book's products |
| **In person / Gift / Other (print)** | Book Code printed in the book (QR + code) | checksum + registered batch |

- One redemption per **(proof, book)**; a multi-book Etsy/Shopify order counts each book separately.
- Etsy order not (yet) in the data → solve stored as **PENDING**, event *Verification Pending*; every
  new data arrival (CSV import, API poll job, admin approval) re-checks pending solves → approved →
  reward + *Verification Approved* + *Case Solved* events.
- **Book Code**: 12 characters from `23456789ABCDEFGHJKLMNPQRSTUVWXYZ` (no 0/O/1/I), shown as
  `XXXX-XXXX-XXXX`, last character = mod-32 Luhn checksum (catches every single typo and adjacent swaps).
  `forge vault codes <out_dir> --count N --channel print|shopify_digital` writes a batch CSV + one code
  page per printed copy (variable data PDF: code + QR to `/solve/<book_id>?code=…`).

## 4. Customer identity, counter, abuse limits

- Customer = e-mail (trimmed, lower-case).
- A proof is bound to the **first e-mail that redeems it successfully**; another e-mail reusing it is
  rejected and written to the **fraud log**.
- Counter = number of **distinct books** solved with a valid proof, per e-mail. Solving the same book
  again does not count twice.
- Rate limits (config `limits`): per IP, per e-mail and per proof+book (wrong answers), with temporary
  lock-out. Answers like 4-digit codes are guessable, so wrong answers lock the proof for the book.
- Account page via **magic link** (signed, 30 min): cases solved, coupons (code, platform, expiry, used),
  progress to milestone 5.

## 5. Reward form & newsletter consent

Order of fields: book (pre-selected from the QR) → final answer (one or two fields by `answer_type`) →
purchase place (Etsy / Shopify / In person / Gift / Other) → proof (Etsy order number **required** for
Etsy) → e-mail → country → newsletter checkbox → Terms & Privacy checkbox → Cloudflare Turnstile.

- Newsletter checkbox: **required to submit** (owner rule) but **never pre-ticked**, separate from
  Terms/Privacy, wording states what is sent and "unsubscribe anytime". Stored proof of consent: time,
  IP, exact wording, form version, country.
- `consent.required_by_region`: EU/EEA + UK customers get an **optional** newsletter box (default on;
  legal review of CASL / CAN-SPAM / GDPR recommended to the owner before launch).
- Unsubscribing never removes earned coupons; transactional reward e-mails are still sent.
- Reviews are never requested or rewarded.

## 6. Rewards

| distinct books solved | reward |
|---|---|
| 1 | 10 % coupon |
| 2 | 20 % |
| 3 | 30 % |
| 4 | 40 % |
| 5 | **free new book set** (gift) |
| 6, 7, … | cycle repeats (10 %, 20 %, …) — config `rewards.cycle: true` |

Coupons: single use, valid 90 days, not stackable. Platform defaults to the purchase place (in person /
gift / other → Shopify); the customer may switch Etsy ⇄ Shopify on the form.

- **ShopifyCouponProvider** (recommended): Admin GraphQL `discountCodeBasicCreate` per customer —
  code `CV-<random>`, `usageLimit: 1`, `appliesOncePerCustomer: true`, `endsAt = now + 90 d`,
  `combinesWith` all false, percentage = tier. Our DB knows the exact code before the e-mail goes out,
  so the Klaviyo flow just prints `{{ event.coupon_code }}`. (Klaviyo's own Shopify unique-coupon blocks
  are not used: the code would exist only inside Klaviyo, tier logic would be duplicated in the flow
  and the account page could not show it.)
- **EtsyCouponPool**: the owner creates codes per tier (10/20/30/40 %) in Etsy Shop Manager and imports
  a CSV (`tier,code,expires`); the site hands out unused codes; Telegram alert when a tier has < 20 left.
  The Etsy Open API v3 has no public endpoint to create shop coupons (checked 2026-11-07 via
  public sources; re-check when the app gets access) → pool stays the mechanism.
- **Milestone 5 gift**: customer chooses one digital book on the account page → Shopify 100 % code
  limited to that product (single use, 90 days) — or, if the owner prefers, a gift request appears in the
  admin and the owner sends an expiring download link to a personalised PDF made with
  `forge edition stamp`. Print gift → a voucher handled manually by the owner (admin task + Telegram).

## 7. E-mail via Klaviyo (`KlaviyoProvider`)

Every valid correct solve → automatic e-mail via a Klaviyo **Flow** triggered by the metric:

- Profile upsert (`/api/profile-import`): email, first name, properties `purchase_place`,
  `cases_solved`, `books_solved`, `current_tier`, `country`.
- Newsletter: subscribe to list **"Case Vault Newsletter"** (`/api/profile-subscription-bulk-create-jobs`)
  only with consent (custom source "Case Vault form vN").
- Events (`/api/events`): **Case Solved** {book_title, sku, solve_count, reward_tier, coupon_code,
  coupon_platform, coupon_expires, certificate_url, next_milestone, progress_text}, **Verification
  Pending**, **Verification Approved**, **Login Link** {login_url}.
- Certificate: PDF generated by the site, linked (Klaviyo flows cannot attach files).
- Klaviyo down → the event stays in the site outbox with retry + Telegram alert; the reward itself is
  stored before any e-mail, so nothing is lost. Setup guide: `docs/KLAVIYO_SETUP.md` (Vietnamese).

## 8. Admin

Separate login (scrypt password hash) + **TOTP 2FA** (RFC 6238, any authenticator app). Pages: books
(auto-registered on APPROVED), solves, correct/wrong rate per book, customers, Etsy verification (CSV
upload, manual approve/reject of pending), coupon stock (+ Etsy pool CSV import), CSV export of e-mails
(**consenting customers only**), fraud log, gift requests. Telegram message on every solved case.

## 9. Secrets & hosting

API keys (Klaviyo, Shopify, Etsy, Turnstile, Telegram, VAULT_ADMIN_TOKEN, VAULT_ANSWER_KEY,
SECRET_KEY) live only in `apps/casevault/.env` on the server (template `.env.example`), never committed.
Deploy guide (Vietnamese): `docs/DEPLOY_CASEVAULT.md` — Docker Compose + Caddy (auto HTTPS) on an
Oracle Cloud VM, or Cloudflare Tunnel from the home VM; daily Postgres backup.

## 10. Data model (site DB; merge plan in INTEGRATION_HALOSPARK.md §7)

`books`, `book_answers`, `book_codes`, `customers`, `consents`, `proofs`, `solves`, `rewards`,
`coupon_pool`, `etsy_orders`, `outbox`, `fraud_log`, `attempts`, `admins`, `gift_requests`.
