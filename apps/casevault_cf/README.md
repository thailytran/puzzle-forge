# CaseVault on Cloudflare (casevault.colorilax.com) — v1.0.0

Implements the owner spec "Đặc tả cho Studio: Website CaseVault" (claude.ai/artifact/RyCfS8phh9et8C18ttBZ8E,
locked 2026-11-21). Replaces the Oracle/Python plan of `apps/casevault` for production; the Python app
stays as reference. One Worker + one D1 database + the existing R2 bucket `colorilax-books`.

```
src/00_util.js        crypto, answer normalisation (= forge/vault/answers.py), Book Codes, CSV, TOTP
src/10_db.js          D1 helpers, encrypted settings, point rules, rate limits
src/20_providers.js   ZeptoMail/Resend, Klaviyo, Shopify discounts, Telegram, Turnstile, outbox
src/30_rewards.js     accounts, proof of purchase, points/tiers, coupons, series gift, redeem, daily jobs
src/40_pages.js       public site (home, case files, result, claim, sign-in link, Detective File)
src/50_admin.js       owner admin (password + TOTP) + internal API for Puzzle Forge / download pages
src/90_router.js      routes, cron
schema.sql            D1 tables (also applied automatically on first request)
build.mjs             -> dist/worker.js (single ES module, no dependencies)
```

`npm test` builds and runs the end-to-end tests (node:sqlite stands in for D1; no network).

## Bindings & secrets (Cloudflare dashboard → Worker → Settings)

| name | kind | value |
|---|---|---|
| `DB` | D1 | database `casevault` (staging: `casevault-staging`) |
| `FILES`, `BOOKS` | R2 | bucket `colorilax-books` (covers + backups under `casevault/`; gift downloads) |
| `ENV_NAME` | var | `production` / `staging` |
| `SITE_URL` | var | `https://casevault.colorilax.com` |
| `VAULT_ADMIN_TOKEN` | **secret (owner)** | same as `VAULT_ADMIN_TOKEN` in the Forge `.env`; also the first-setup token of /admin |
| `VAULT_ANSWER_KEY` | **secret (owner)** | same as `VAULT_ANSWER_KEY` in the Forge `.env` |
| `MASTER_KEY` | secret, optional | encrypts the keys saved in /admin → Settings (default: derived from VAULT_ADMIN_TOKEN) |

Cron triggers: `*/10 * * * *` (outbox retries) and `17 4 * * *` (daily: birthdays, expiry, releases,
pending Etsy re-check, backup to R2 kept 30 days).

Shopify, Klaviyo, Turnstile, Telegram and mail keys are typed by the owner in /admin → Settings
(stored AES-GCM encrypted, never shown again).

## Free Book (1.3.0)

- `POST /free-book/claim {email, handle, source, consent}` — from colorilax.com/pages/free-book (CORS: colorilax.com, *.myshopify.com, *.shopifypreview.com). One book per e-mail (Gmail dots / +tags, case ignored); a repeat gets the old book link again. 5 requests / hour / IP; disposable domains refused.
- Books are read from Shopify (product type `Free Book`, ACTIVE, metafield `free_book.file_key` under `free/`) every 10 minutes into D1 `free_books`.
- `GET /free-book/dl/<token>` streams the PDF from R2 `BOOKS` for 7 days. `GET /free-book/books` lists the books.
- Outbox: mail "Your free book is ready", Klaviyo event `Claimed Free Book` with profile `freebook_choice`, `interest`, `source`; consent → list subscription. Needs in /admin → Settings: Shopify shop + token (read_products), mail provider + token, Klaviyo key + list.

## Internal API (Bearer VAULT_ADMIN_TOKEN)

- `POST /api/admin/books` — Puzzle Forge book package(s) (`forge vault sync`): hashes only.
- `POST /api/internal/bookcode {book_id, order}` — one fresh Book Code for a Shopify order (download pages).
- `GET /api/internal/health`.
