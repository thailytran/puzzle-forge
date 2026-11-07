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
- [ ] P1.6 Book builder: progressive / mixed / by_section modes, front matter, TOC, solutions section, `forge book build` + `forge book verify`.
- [ ] P1.7 QA preflight + `qa_report.md` + preview PNGs.

## PQ — QA gate (before the P1 milestone; see docs/QA_SPEC.md)
- [ ] PQ.1 QA framework: check registry (id, BLOCKER/MAJOR/MINOR, evidence), book state machine with history (SQLite), report hash lock (interior/cover/manifest sha256), waivers, auto-fix loop hook.
- [ ] PQ.2 L1 per-puzzle checks: dual solver, uniqueness, type rules, difficulty band, kid safety, catalog uniqueness.
- [ ] PQ.3 L2 per-page checks + data extraction from the rendered PDF ("printed = verified"), thumbnails.
- [ ] PQ.4 L3 book checks (counts, distribution, TOC, matter, placeholders) + proofread (dictionary now, AI after P2).
- [ ] PQ.5 qa_report.json + qa_report.html, `forge qa run`, `forge book status`, `forge review --approve|--reject`.

- [ ] P1.8 **Milestone**: build 3 sample books (kids word search, adult mixed, large-print sudoku); done only when all 3 reach **QA_PASSED**; owner reviews PDFs + QA reports.

## P2 — AI content layer (≈2 weeks)
- [ ] P2.1 LLM client (Anthropic default, OpenAI optional), prompt files, JSON-schema validation + retry, SQLite cache, cost tracking.
- [ ] P2.2 Word lists: theme → sub-themes → words by audience; dictionary check, length rules, kid-safety filter.
- [ ] P2.3 Crossword clues by level (definition / fill-in / wordplay), clue-answer check.
- [ ] P2.4 Book ideation: niche + title/subtitle + 100 puzzle themes from one prompt; `listing.json` copy.
- [ ] P2.5 Batch: build N books from a CSV of briefs.

## P3 — Mystery engine (≈4–5 weeks) → first mystery book (docs/MYSTERY_DESIGN.md §5, §9–§12)
- [ ] P3.1 Logic grid: seeded generator (easy → extreme), propagation solver 1, brute-force / CP-SAT solver 2, unique solution, English clue templates + AI rephrase round-trip check, constraint `grid_solution`; property test 200 seeds.
- [ ] P3.2 Causal graph (`forge/mystery/causal_graph.py`): nodes fact/evidence/knot/puzzle/chapter/final, requires/unlocks, state filtering, closure, DAG + reachability + ≥2 evidence checks, reveal rules.
- [ ] P3.3 Stage framework: S1–S10 runner, YAML between stages, `--from-stage`, validation + retry, recorded-fixture AI client for tests.
- [ ] P3.4 Stages S1–S4: brief, characters, relationships, truth timeline + validators (QA L4.timeline, L4.relations).
- [ ] P3.5 Stages S5–S7: story arc, clue graph, evidence ↔ constrained puzzles (tokens for every evidence).
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
- [ ] P4.4 SKU: Portal format `BRAND-AUD-LINE-FMT-NNNN-SGL|SERnnn-vv` (`configs/sku.yaml`), Product Hub API when reachable, local unique counter fallback; state SKU_ASSIGNED.
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
