# ROADMAP — Puzzle Forge

Tick `[x]` when a task is merged. Each task ≈ one Claude Code session = one PR.
**Done means**: tests pass, ruff clean, docs/commands updated, owner can run it on the VM.

## P0 — Foundation (≈1 week)
- [x] P0.1 Scaffold: uv project, `forge` package, typer CLI, ruff/mypy/pytest, `.env.example`, `.gitignore`, GitHub Actions CI (lint + tests).
- [x] P0.2 Core models (`forge/core`): PuzzleSpec, Puzzle, DifficultyScore, VerifyReport, BookSpec (YAML loader), seed utils, canonical hashing.
- [x] P0.3 SQLite registry: store puzzles by content_hash, reject duplicates, list by book.
- [x] P0.4 Typst pipeline: `templates/typst/book.typ`, trim/margin table (8.5x11, 6x9, 8x10, 8.5x8.5), even page count, fonts (OFL) in `assets/fonts/`, `forge layout demo` → sample PDF.
- [ ] P0.5 VM install for the owner's **personal Ubuntu 24.04 VM**: idempotent `scripts/setup_vm.sh` (apt deps, uv, Python 3.12, typst binary pinned version, fonts, `uv sync`, create `.env` from `.env.example`, `forge doctor` self-check), `docs/INSTALL_VM.md` in **Vietnamese** with copy-paste steps (incl. cloning a **private** repo via `gh auth login` or a deploy key), plus `scripts/update.sh` (git pull + uv sync + tests).
- [ ] P0.6 `forge doctor`: checks Python, typst, fonts, write access to `output/`, DB, optional API keys; prints a green/red table.

## P1 — Puzzle Engine MVP (≈2–3 weeks) → first classic KDP book
- [ ] P1.1 Word search: generator (directions by level, masks), solver, difficulty, SVG/Typst render, solution render; constraint `hidden_message`.
- [ ] P1.2 Sudoku (rustoku): 4x4/6x6/9x9, levels, uniqueness, difficulty from technique trace, render; constraint `shaded_cells`.
- [ ] P1.3 Maze: generator + solver, sizes by level, SVG render, solution path; constraint `path_letters`.
- [ ] P1.4 Word scramble + Cryptogram: unique answers, quote source = own/public domain only.
- [ ] P1.5 Crossword (own filler, no GPL): grid templates by size, fill from word list, numbering, clue list render.
- [ ] P1.6 Book builder: progressive / mixed / by_section modes, front matter, TOC, solutions section, `forge book build` + `forge book verify`.
- [ ] P1.7 QA preflight + `qa_report.md` + preview PNGs.
- [ ] P1.8 **Milestone**: build 3 sample books (kids word search, adult mixed, large-print sudoku) and review PDFs.

## P2 — AI content layer (≈2 weeks)
- [ ] P2.1 LLM client (Anthropic default, OpenAI optional), prompt files, JSON-schema validation + retry, SQLite cache, cost tracking.
- [ ] P2.2 Word lists: theme → sub-themes → words by audience; dictionary check, length rules, kid-safety filter.
- [ ] P2.3 Crossword clues by level (definition / fill-in / wordplay), clue-answer check.
- [ ] P2.4 Book ideation: niche + title/subtitle + 100 puzzle themes from one prompt; `listing.json` copy.
- [ ] P2.5 Batch: build N books from a CSV of briefs.

## P3 — Mystery engine (≈3–4 weeks) → first mystery book
- [ ] P3.1 Logic grid generator + solver (3x3 → 6x6), unique solution, strategy-based difficulty, constraint `grid_solution`.
- [ ] P3.2 Case Bible + Clue Graph models, validators (DAG, fair play, ≥2 evidence/knot).
- [ ] P3.3 AI stages: brief → bible → clue graph (with validation loops), editable YAML between stages.
- [ ] P3.4 Encoders (token → page number etc.) + chapter planner + page planner with dead-end pages.
- [ ] P3.5 Constrained puzzle generation for every evidence token.
- [ ] P3.6 Prose + case documents (letters, clippings, interrogations) with spoiler guard; Typst mystery templates (case-file look, evidence board).
- [ ] P3.7 Meta-puzzle + finale + solutions with reasoning.
- [ ] P3.8 AI playtest agent + report; fix loop.
- [ ] P3.9 **Milestone**: `lighthouse` (adult) and `museum_kids` (kids) books built and reviewed.

## P4 — Series & publishing (≈2 weeks)
- [ ] P4.1 Series bible, `forge series new/next`, continuity checks, cross-volume dedupe.
- [ ] P4.2 Cover generator (Typst: front/spine/back from KDP page count + paper type; image slot for art).
- [ ] P4.3 Export package + checklist for KDP upload.

## P5 — Web UI & API (≈2 weeks)
- [ ] P5.1 FastAPI: jobs queue (SQLite), build/verify endpoints, download outputs.
- [ ] P5.2 Simple web UI (browser-only, works over Tailscale): briefs, job status, PDF preview, approve/regenerate.
- [ ] P5.3 Auth (single owner login) + Telegram notify on job done.
- [ ] P5.4 API contract for HALOSPARK Studio to enqueue jobs (doc only, no coupling).

## P6 — Illustrations & extras (parallel / later)
- [ ] P6.1 Image slots + prompt export for illustrations (scenes, props) to be made by the HALOSPARK image tool; import + 300 DPI check.
- [ ] P6.2 More puzzle types (nonogram, kakuro, futoshiki, hashi…), spot-the-difference for kids.
