# CaseVault (Cloudflare) changelog

## 1.2.0 — 2026-11-21
- Logo name "Colorilax Case Vault" (header + page titles). Site identity images drawn by Gemini through Studio (emblem, hero background, icons) are served from R2 `casevault/site/` at `/assets/<name>`; the page falls back to plain colours until they are uploaded.

## 1.1.0 — 2026-11-21
- Customer sign-in with e-mail + password (reset link by e-mail) or "Continue with Google" (owner sets the Google OAuth client in /admin → Settings). The e-mail sign-in-link-only flow is gone.
- Admin: password only by default; authenticator-app two-step is optional (/admin → Security). No SMS.
- Wrong answers can be retried as often as needed (30-second pause after 5 misses in 10 minutes, anti-bot). Each Etsy order + book (SKU) and each Book Code still gives one reward only.
- Footer: © Colorilax · HaloSpark e-Commerce Inc. + "created with the help of AI tools" note on every page.

## 1.0.0 — 2026-11-21
- First version: answer check + extended ending, Etsy order / Book Code verification, 15% next-book coupons, Case Points and ranks, series gift, redeem, Klaviyo events, owner admin, daily backup.

## 1.3.0 (2026-11-22)
- Free Book: POST /free-book/claim, GET /free-book/dl/<token>, GET /free-book/books; D1 free_books + free_claims; Klaviyo "Claimed Free Book"; tests.
