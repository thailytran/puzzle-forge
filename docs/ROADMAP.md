# ROADMAP — Puzzle Forge

Tick `[x]` when a task is done (tests + QA pass). Each task ≈ one Claude Code session = one PR.
**Done means**: tests pass, ruff clean, docs/commands updated, owner can run it on the VM.

## P0 — Foundation (≈1 week)
- [x] P0.1 Scaffold: uv project, `forge` package, typer CLI, ruff/mypy/pytest, `.env.example`, `.gitignore`, GitHub Actions CI (lint + tests).
- [x] P0.2 Core models (`forge/core`): PuzzleSpec, Puzzle, DifficultyScore, VerifyReport, BookSpec (YAML loader), seed utils, canonical hashing.
- [x] P0.3 SQLite registry: store puzzles by content_hash, reject duplicates, list by book.
- [x] P0.4 Typst pipeline: `templates/typst/book.typ`, trim/margin table (8.5x11, 6x9, 8x10, 8.5x8.5), even page count, fonts (OFL) in `assets/fonts/`, `forge layout demo` → sample PDF.
- [x] P0.5 VM install for the owner's **personal Ubuntu 24.04 VM**: idempotent `scripts/setup_vm.sh` (apt deps, uv, Python 3.12, typst binary pinned version, fonts, `uv sync`, create `.env` from `.env.example`, `forge doctor` self-check), `docs/INSTALL_VM.md` in **Vietnamese** with copy-paste steps (incl. cloning a **private** repo via `gh auth login` or a deploy key), plus `scripts/update.sh` (git pull + uv sync + tests).
- [x] P0.6 `forge doctor`: checks Python, typst, fonts, write access to `output/`, DB, optional API keys; prints a green/red table.

## P1 — Puzzle Engine MVP (≈2–3 weeks) → first classic KDP book
- [x] P1.1 Word search: generator (directions by level, masks), solver, difficulty, SVG/Typst render, solution render; constraint `hidden_message`.
- [x] P1.2 Sudoku (rustoku): 4x4/6x6/9x9, levels, uniqueness, difficulty from technique trace, render; constraint `shaded_cells`.
- [x] P1.3 Maze: generator + solver, sizes by level, SVG render, solution path; constraint `path_letters`.
- [x] P1.4 Word scramble + Cryptogram: unique answers, quote source = own/public domain only.
- [x] P1.5 Crossword (own filler, no GPL): grid templates by size, fill from word list, numbering, clue list render.
- [x] P1.6 Book builder: progressive / mixed / by_section modes, front matter, TOC, solutions section, `forge book build` + `forge book verify`.
- [x] P1.7 QA preflight + report + preview PNGs → merged into PQ.3 (preflight, thumbnails) and PQ.5 (report).

## PQ — QA gate (before the P1 milestone; see docs/QA_SPEC.md)
- [x] PQ.1 QA framework: check registry (id, BLOCKER/MAJOR/MINOR, evidence), book state machine with history (SQLite), report hash lock (interior/cover/manifest sha256), waivers, auto-fix loop hook.
- [x] PQ.2 L1 per-puzzle checks: dual solver, uniqueness, type rules, difficulty band, kid safety, catalog uniqueness.
- [x] PQ.3 L2 per-page checks + data extraction from the rendered PDF ("printed = verified"), thumbnails.
- [x] PQ.4 L3 book checks (counts, distribution, TOC, matter, placeholders) + proofread (dictionary now, AI after P2).
- [x] PQ.5 qa_report.json + qa_report.html, `forge qa run`, `forge book status`, `forge review --approve|--reject`.

## PC — Content plan & richness (owner rules 2026-11-07; P1.8-v2 is built with these)
- [ ] PC.1 `configs/content_rules.yaml` + loader; generators take targets from it (word search counts/grids/coverage, cryptogram letters/page, scramble lengths, sudoku grids/page, maze title + illustration slot).
- [ ] PC.2 Multi-puzzle pages: sudoku 2–6 grids per page (kids 4×4/6×6, adult 9×9 2 or 4 Easy), large print 1.
- [x] PC.3 Content plan: `content_plan.yaml` schema + validator (unique sub-themes, words in dictionary/glossary, age fit, ≤ 2 uses per word), builder reads it, `--from-stage puzzles`, `illustration_requests.json`.
- [ ] PC.4 AI content planner (needs P2.1): theme → sub-themes → per-page words / quotes / illustration descriptions; AI relevance scores.
- [ ] PC.5 QA richness: L3.richness_counts, ws_coverage, page_fill, diversity, theme_relevance, age_fit.
- [ ] PC.6 Rebuild the 3 sample books as **P1.8-v2** (content plans + rules) → QA_PASSED → review pack.

## PE — Editions, brand watermark, personalisation (owner rules 2026-11-07)
- [x] PE.1 `configs/brand.yaml` + placeholder logo/emblem; copyright & licence page from brand (personal use; classroom copies for printed escape rooms).
- [x] PE.2 Watermark layer in Typst (pre-tinted emblem, knock-out panels under functional blocks) + corner logo + footer microtext.
- [x] PE.3 Editions: `editions: [digital, spiral]`; digital Letter + A4; spiral binding margin (coil/wire-o), simplex/duplex, colour + grayscale, bleed + crop marks, single-sided cut-out pages; `forge edition build`.
- [x] PE.4 `forge edition stamp` (buyer footer, metadata, micro-pattern, print-only permissions) + `forge edition trace`.
- [x] PE.5 QA: watermark knock-out/contrast, binding margin, bleed/crop marks, stamp-vs-master diff.
- [ ] PE.6 Escape-room sample book in both editions (after P3) + review pack.

## PB — Blueprints, page planner, framed art, colour-by-number (owner rules 2026-11-07)
- [x] PB.1 Blueprint library: `blueprints/escape_adult/line.yaml` (page types, zones in mm, z-order, variants) + loader + `forge blueprint preview` (coloured zones PDF).
- [x] PB.2 CBN level 1: geometric mosaic (square/hex/Voronoi) with embedded code glyph, type A + type B, palette + legend, glyph-matching solver, QA L1.cbn_reveal, coloured solution.
- [ ] PB.3 Page planner: case bible + arc + clue graph + blueprint + targets → `page_plan.yaml` (+ validation, `--from-stage page_plan`), hints (4 tiers), code register / host pack.
- [ ] PB.4 Art requests: per art zone pixel size + mask PNG + style bible + prompt clauses; `art_requests/` export, `forge art import`; compositor layers; QA L2.art_*.
- [ ] PB.5 Escape sample book ≥ 50 game pages with 1–2 cbn_reveal pages (needs P3 case data) + review pack.
- [ ] PB.6 CBN level 2: line art from the HALOSPARK image tool → vector regions → glyph-split regions.
- [ ] PB.7 Blueprints escape_kids, mystery_adult, adventure_kids.

- [ ] P1.8 **Milestone**: build 3 sample books (kids word search, adult mixed, large-print sudoku); done only when all 3 reach **QA_PASSED**; owner reviews PDFs + QA reports via `review/P1.8.md` (`forge review-pack`).

## P2 — AI content layer (≈2 weeks)
- [ ] P2.1 (needed by PC.4) LLM client (Anthropic default, OpenAI optional), prompt files, JSON-schema validation + retry, SQLite cache, cost tracking.
- [ ] P2.2 Word lists: theme → sub-themes → words by audience; dictionary check, length rules, kid-safety filter.
- [ ] P2.3 Crossword clues by level (definition / fill-in / wordplay), clue-answer check.
- [ ] P2.4 Book ideation: niche + title/subtitle + 100 puzzle themes from one prompt; `listing.json` copy.
- [ ] P2.5 Batch: build N books from a CSV of briefs.

## P3 — Mystery engine (≈4–5 weeks) → first mystery book (docs/MYSTERY_DESIGN.md §5, §9–§12)
- [ ] P3.1 Logic grid: seeded generator (easy → extreme), propagation solver 1, brute-force / CP-SAT solver 2, unique solution, English clue templates + AI rephrase round-trip check, constraint `grid_solution`; property test 200 seeds.
- [ ] P3.2 Causal graph (`forge/mystery/causal_graph.py`): nodes fact/evidence/knot/puzzle/chapter/final, requires/unlocks, state filtering, closure, DAG + reachability + ≥2 evidence checks, reveal rules.
- [ ] P3.3 Stage framework: S1–S10 runner, YAML between stages, `--from-stage`, validation + retry, recorded-fixture AI client for tests.
- [ ] P3.4 Stages S1–S4: brief (+ setting relationship ontology), characters (tiered secrets, hidden agendas), relationships (directed graph: inverses, conflict pairs, no isolated character), truth timeline (≥ 12 checkpoints) + validators (QA L4.timeline, L4.relations).
- [ ] P3.5 Stages S5–S7: 4-act story arc with reader objectives, clue graph, clues (real/red herring, tier, location, discovery) ↔ case artifacts ↔ constrained puzzles (tokens for every evidence); review dashboard `case.html`.
- [ ] P3.6 Encoders (token → page number) + chapter/page planner with dead-end pages; Typst mystery templates (case file, evidence board).
- [ ] P3.7 Stage S8: grounded prose + case documents with spoiler guard and reveal rules.
- [ ] P3.8 `forge/qa/reader_sim.py` + L4 checks (graph, reader sim, case uniqueness via logic engine, spoilers, solution text); 3-chapter hand-written fixture case.
- [ ] P3.9 Meta-puzzle + finale + solutions with step-by-step reasoning; `mystery_book.json` + `forge mystery export-play` (html / escaperoom).
- [ ] P3.10 AI play-test: 2 agents, different models (Claude + GPT), on the export; L4.playtest in the report.
- [ ] P3.11 **Milestone**: `lighthouse` (adult) and `museum_kids` (kids) built, **QA_PASSED**, reviewed.

## P4 — Series & publishing (≈2 weeks)
- [ ] P4.1 Series bible, `forge series new/next`, continuity checks, cross-volume dedupe.
- [ ] P4.2 Cover generator (Typst: front/spine/back from KDP page count + paper type; image slot for art).
- [ ] P4.3 Export package + checklist for KDP upload.
- [x] P4.4 SKU: Portal format, `SkuPort` with `HubSkuProvider` (Product Hub shared counter, `X-Hub-Token`) and `DevSkuProvider` (tests, `DEV-` prefix), age codes KID1/KID4/KID9/TEEN/ADULT/SENIOR, `forge sku assign` (QA_PASSED → SKU_ASSIGNED).
- [ ] P4.5 book_card.json (AI text + code facts, spine width, sample pages 300 DPI) + L5 checks → METADATA_READY.
- [ ] P4.6 Marketing handoff: marketing_brief.json in the Portal (Coloring Page) schema, `forge marketing prompt <book_id>` (OpenAI master prompt), image set plan; code composites real pages/text, AI only backgrounds.

## P5 — Web UI & API (≈2 weeks)
- [ ] P5.1 FastAPI: jobs queue (SQLite), build/verify endpoints, download outputs.
- [ ] P5.2 Simple web UI (browser-only, works over Tailscale): briefs, job status, PDF preview, approve/regenerate.
- [ ] P5.3 Auth (single owner login) + Telegram notify on job done.
- [ ] P5.4 API contract for HALOSPARK Studio to enqueue jobs (doc only, no coupling).

## P6 — Illustrations & extras (parallel / later)
- [ ] P6.1 Image slots + prompt export for illustrations (scenes, props) to be made by the HALOSPARK image tool; import + 300 DPI check.
- [ ] P6.2 More puzzle types (nonogram, kakuro, futoshiki, hashi…), spot-the-difference for kids.

## P7 — HALOSPARK SUITE integration (docs/INTEGRATION_HALOSPARK.md)
- [ ] P7.1 Ports wired through the core (registry, state, SKU, research, listing, notification); CLI builds adapters from `.env`.
- [ ] P7.2 Hub changes (in halospark-suite): age-code migration (KID1/KID4/KID9/TEEN/ADULT/SENIOR, aliases) + idempotent `external_id` on `POST api/products`.
- [ ] P7.3 Postgres adapters for registry/state/QA reports + SQLite → Postgres import.
- [ ] P7.4 ResearchInputPort adapter: approved `PZL` ideas from the Hub → book briefs.
- [ ] P7.5 ListingOutputPort adapter: Hub assets + `produced` → SEO Listing module.
- [ ] P7.6 Puzzle Forge as a Suite tool (tool.json, portal auth, hooks API, Telegram notifications).

## P8 — CBN Mystery line (docs/MYSTERY_DESIGN.md §15–§16)
- [x] P8.1 "All clues required" engine `forge/mystery/necessity.py` (candidate spaces: suspects × attributes, codes, locations; declarative clue predicates) + QA `L4.all_clues_required` (drop any clue → > 1 candidate) for every escape/mystery/adventure line.
- [ ] P8.2 Blueprint `cbn_mystery` (kids + adult): chapter = story page + cbn_reveal + evidence card; final deduction page; `case_vault` last page.
- [ ] P8.3 Case builder: suspects/codes + reveal glyphs → clues that pass P8.1; CBN pages generated with the glyph constraint (PB.2 engine).
- [ ] P8.4 Sample CBN Mystery book (kids + adult) → QA_PASSED → review pack.

## P9 — Case Vault website & rewards (docs/CASEVAULT.md)
- [x] P9.1 Docs + config: CASEVAULT.md, KLAVIYO_SETUP.md (vi), DEPLOY_CASEVAULT.md (vi), `apps/casevault/config/casevault.yaml`, `.env.example`.
- [x] P9.2 `forge/vault`: answer normalisation + HMAC, Book Codes (checksum, batches CSV, code pages PDF), registration payload, outbox with retry, `forge vault init/sync/status/codes`, auto-enqueue on APPROVED.
- [x] P9.3 `case_vault` last page: "Submit your final answer at <DOMAIN>" + QR (segno, BSD) → `/solve/<book_id>`; QA `L4.vault_page`.
- [x] P9.4 `apps/casevault` core: DB models, admin book API, answer check, proofs (Book Code, Etsy API + CSV, Shopify order), binding to first e-mail, counter, rate limits, pending → approved re-check.
- [x] P9.5 Rewards + providers: tiers 10/20/30/40/gift (cycle), ShopifyCouponProvider, EtsyCouponPool (+ low-stock alert), KlaviyoProvider (profile, list consent, events), outbox retry, Telegram, certificate PDF, magic-link account page.
- [x] P9.6 Public form (HTMX) with consent rules by region + Turnstile; admin (password + TOTP): books, solves, stats, customers, Etsy CSV/pending, coupon stock, consenting e-mail export, fraud log, gift requests.
- [ ] P9.7 Docker image + Compose + Caddy, Cloudflare Tunnel option, daily backup script; E2E tests with mocked Etsy/Shopify/Klaviyo.
- [ ] P9.8 **Go-live** (owner): domain, Klaviyo flows, Shopify app token, Etsy app key, legal review of consent wording.
