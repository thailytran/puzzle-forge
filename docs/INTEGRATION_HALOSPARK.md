# INTEGRATION — Puzzle Forge ⇄ HALOSPARK SUITE

Goal: Puzzle Forge runs standalone today and becomes a **module of HALOSPARK SUITE** later
(shared database, shared Research input and Listing output) **through adapters only**.
The core never imports Halospark code. Facts below were read from `thailytran/halospark-suite`
3.1.0 (`tools/product-hub`) on 2026-11-07.

## 1. Ports & adapters

| Port (`forge/ports`) | Purpose | Standalone adapter (now) | Suite adapter (P7) |
|---|---|---|---|
| `PuzzleRegistryPort` | catalog-wide puzzle dedupe | `forge.core.registry.Registry` (SQLite `data/forge.db`) | table `forge_puzzles` in the Suite Postgres |
| `BookStatePort` | book state machine + history | `forge.qa.state.StateStore` (SQLite) | `forge_book_states` in Postgres, mirrored to Hub `product_events` |
| `SkuPort` | SKU from the shared counter | `HubSkuProvider` (HTTP to Product Hub) — **primary**; `DevSkuProvider` (tests only, `DEV-` prefix) | same `HubSkuProvider`, or an in-process call when running inside the Suite |
| `ResearchInputPort` | book ideas / niches in | CSV/YAML briefs (P2.5) | Hub `GET api/products?status=approved&line=PZL` (ideas created by Etsy Research → Hub) |
| `ListingOutputPort` | approved book out | files in `output/<book_id>/` | Hub `POST api/products/{sku}/assets` + `POST api/products/{sku}/produced {title, book_json, listing_copy}` → Module 3 (SEO Listing) |
| `NotificationPort` | job done / QA failed | console | Portal Telegram (`portal/app/telegram.py`) |

Rules: core packages (`core`, `puzzles`, `book`, `qa`, `mystery`, `layout`) take ports as arguments;
only `forge/cli.py` / `forge/api` wire concrete adapters (from `.env`). Tests use fakes.

## 2. SKU contract (existing Hub API — no Hub change needed to start)

```
POST {HUB_URL}/api/products            HUB_URL = https://<portal>/hooks/product-hub
Header: X-Hub-Token: <token>           (Product Hub: connection 'product-hub', env HUB_TOKEN, or data/hub_token.txt)
Body:   {"topic": "<title>", "title": "<title>", "audience": "KID4", "line": "PZL", "format": "PBK",
         "brand": "HSP", "source": "puzzle-forge", "keyword_main": "", "keywords": [],
         "note": "puzzle-forge book_id=<id>", "series_id"?: n, "volume_no"?: n}
200 →   product row: {"sku": "HSP-KID4-PZL-PBK-0007-SGL", "status": "idea", ...}
401 →   bad / missing token
```

- Format: `BRAND-AUD-LINE-FMT-NNNN-SGL` or `...-NNNN-SERnnn-vv`; the counter is per prefix
  `BRAND-AUD-LINE-FMT` in Postgres (`sku_counters`, `next_sku()`), safe under concurrency.
- The Hub stores `audience` as given (it only maps `kids/adult/toddler/teen` words to codes), so new
  codes work as soon as they exist in settings (for the UI and classification).
- Puzzle Forge keeps the SKU in `output/<book_id>/sku.json`, so assigning is idempotent on our side.

### 2.1 Endpoint additions proposed for the Hub
1. **Idempotency**: accept `external_id` in `POST api/products` (unique per `source`); if a product
   with the same `(source, external_id)` exists, return it instead of issuing a new SKU. Puzzle Forge
   already sends `external_id = book_id`. Without it, a network retry could burn a number.
2. `GET api/products?source=puzzle-forge&external_id=<book_id>` (lookup for recovery).
3. Optional: `POST api/products/{sku}/events` so Puzzle Forge can mirror its QA states
   (`QA_PASSED`, `APPROVED`, …) into `product_events`.

## 3. Age-group codes — migration proposal (no existing SKU changes)

New codes are named by the **starting age**; old SKUs keep their codes forever.

| New code | Meaning | forge audience | Old Hub code (kept as alias) |
|---|---|---|---|
| `KID1` | 1–3 (reserved) | — | `TOD` |
| `KID4` | 4–8 | `kids_6_8` | `KID` |
| `KID9` | 9–12 | `kids_9_12` | — |
| `TEEN` | 13–17 | `teen` | `TEE` |
| `ADULT` | adults | `adult` | `ADU` |
| `SENIOR` (or `LP`, owner to choose) | large print / seniors | `senior_large_print` | — |

```sql
-- Product Hub (Postgres) — additive only
INSERT INTO settings_audiences(code, name, keywords, ord) VALUES
 ('KID1','Trẻ 1–3 tuổi','toddler|baby',10), ('KID4','Trẻ 4–8 tuổi','kid|kids|children|preschool',11),
 ('KID9','Trẻ 9–12 tuổi','tween|ages 9-12|middle grade',12), ('TEEN','Thiếu niên','teen|teens',13),
 ('ADULT','Người lớn','adult|adults',14), ('SENIOR','Người cao tuổi / chữ lớn','large print|senior',15)
ON CONFLICT (code) DO NOTHING;
-- Optional alias table so reports group old+new codes together:
CREATE TABLE IF NOT EXISTS settings_audience_aliases (alias TEXT PRIMARY KEY, code TEXT NOT NULL);
INSERT INTO settings_audience_aliases VALUES ('KID','KID4'),('TOD','KID1'),('TEE','TEEN'),('ADU','ADULT')
ON CONFLICT DO NOTHING;
```

Note: new codes start new counters (`HSP-ADULT-PZL-PBK-0001`), separate from old `HSP-ADU-…`
prefixes; old SKUs are never re-numbered. Classification code in the Hub (`_prepare_idea`) should map
`kids` → `KID4` once the migration is live.

## 4. Shared data schema (Suite DB, P7)

| Table | Key columns | Notes |
|---|---|---|
| `forge_books` | `book_id` PK, `sku` FK → `products.sku`, `kind` (classic/mystery), `spec_json`, `state` | 1 book ↔ 1 Hub product |
| `forge_book_states` | `id`, `book_id`, `from_state`, `to_state`, `at`, `actor`, `note` | same as SQLite today |
| `forge_puzzles` | `content_hash` PK, `puzzle_id`, `type`, `book_id`, `seed`, `level`, `data_json` | catalog dedupe across all books |
| `forge_qa_reports` | `run_id` PK, `book_id`, `result`, `hashes_json`, `report_json` | hash-locked reports |
| `forge_jobs` | `job_id`, `kind`, `payload`, `status` | P5 job queue |

Files stay on disk / object storage under `products/<SKU>/…` (Hub layout) once a SKU exists:
`interior.pdf`, `cover.pdf`, `book_card.json`, `marketing_brief.json`, `qa/qa_report.html`.

## 5. Integration steps (ROADMAP P7)

1. P7.1 Ports wired everywhere (core takes ports; CLI builds adapters from `.env`) — no behaviour change.
2. P7.2 Hub migration (§3) + idempotent `external_id` (§2.1) merged in halospark-suite.
3. P7.3 Postgres adapters for `PuzzleRegistryPort` / `BookStatePort` (+ one-off SQLite → Postgres import).
4. P7.4 `ResearchInputPort` adapter: approved `PZL` ideas from the Hub become book briefs.
5. P7.5 `ListingOutputPort` adapter: assets + `produced` call; Module 3 lists the book.
6. P7.6 Run as a Suite tool (`tools/puzzle-forge/tool.json`, portal auth, `/hooks/puzzle-forge/api/...`),
   NotificationPort → Portal Telegram.
