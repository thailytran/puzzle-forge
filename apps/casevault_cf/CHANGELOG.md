# CaseVault (Cloudflare) changelog

## 1.4.1
- GET /solve/<book_id> (the QR on every book's last page) opens the home page with that book selected.

## 1.4.0
- Redesign (taste): new vault-dial logo, Outfit/Fraunces/JetBrains Mono, asymmetric hero with the answer form, no emojis (SVG icons), grain, tactile buttons.
- Home: New case files (5 newest), Free coloring books list (from the Shopify free-book cache), shelves, How it works as a numbered list, ranks as a ruled row.

## 1.3.4 — 2026-11-25
- Free Book: the Klaviyo event "Claimed Free Book" now carries `download_url`, so the Klaviyo flow "Free Book Delivery" can send the link from the shop's own sending domain. A repeat claim sends the event again (new unique_id, `resend: true`).
- Free Book e-mail from the Worker uses a Colorilax frame (was headed "Case Vault") and is signed "Lee & Tee from Colorilax".

## 1.3.3 — 2026-11-22
- /admin → Settings → "Connect Shopify": one-time Shopify sign-in (authorization code grant, state + hmac checked) for when the Dev Dashboard app and the store are in different Shopify organisations (client credentials answer shop_not_permitted). The token is stored encrypted as shopify_token. The app needs the redirect URL `https://casevault.colorilax.com/admin/shopify/callback`.

## 1.3.2 — 2026-11-22
- Shopify token errors show Shopify's reason (e.g. invalid_client) in "Send test".

## 1.3.1 — 2026-11-22
- Shopify can now use a Dev Dashboard app: /admin → Settings → `shopify_client_id` + `shopify_client_secret` (client-credentials grant; the ~24 h token is cached encrypted and renewed automatically). `shopify_token` (legacy custom app) still works and wins when set.
- "Send test" in Settings also checks Shopify and shows how many Free Books it can see.
- Claim errors are also returned as `message` (the theme shows j.message).

## 1.3.0 — 2026-11-22
- Free Book: POST /free-book/claim, GET /free-book/dl/<token>, GET /free-book/books; D1 free_books + free_claims; Klaviyo "Claimed Free Book"; tests.

## 1.2.0 — 2026-11-21
- Logo name "Colorilax Case Vault" (header + page titles). Site identity images drawn by Gemini through Studio (emblem, hero background, icons) are served from R2 `casevault/site/` at `/assets/<name>`; the page falls back to plain colours until they are uploaded.

## 1.1.0 — 2026-11-21
- Customer sign-in with e-mail + password (reset link by e-mail) or "Continue with Google" (owner sets the Google OAuth client in /admin → Settings). The e-mail sign-in-link-only flow is gone.
- Admin: password only by default; authenticator-app two-step is optional (/admin → Security). No SMS.
- Wrong answers can be retried as often as needed (30-second pause after 5 misses in 10 minutes, anti-bot). Each Etsy order + book (SKU) and each Book Code still gives one reward only.
- Footer: © Colorilax · HaloSpark e-Commerce Inc. + "created with the help of AI tools" note on every page.

## 1.0.0 — 2026-11-21
- First version: answer check + extended ending, Etsy order / Book Code verification, 15% next-book coupons, Case Points and ranks, series gift, redeem, Klaviyo events, owner admin, daily backup.

## 1.5.0
- Home: "How it works" and "Detective ranks" moved under the answer box, redrawn as infographics with custom icons.
- New case files shown in one fixed size.
- Seasonal castle background switches automatically by date (Christmas, winter, spring, summer, autumn).
- Older, bolder ornate logo.
