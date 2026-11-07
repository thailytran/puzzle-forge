# Changelog

- docs: initial project plan (CLAUDE.md, SPEC, MYSTERY_DESIGN, ROADMAP, PROMPTS)
- P0.1: scaffold (uv project, typer CLI `forge`, ruff/mypy/pytest, .env.example, .gitignore, GitHub Actions CI)
- P0.2: core models (PuzzleSpec, Puzzle, constraints, DifficultyScore, VerifyReport, PuzzleType protocol), BookSpec YAML loader, seed utils, canonical hashing
- P0.3: SQLite registry (content_hash dedupe across books, list by book, `forge registry stats|list`), settings from .env
- P0.4: Typst pipeline: templates/typst/book.typ, KDP trim/margin table (configs/kdp.yaml), even page padding, OFL fonts in assets/fonts, `forge layout demo`; CLI backend with python-package fallback
- P0.6: `forge doctor` (Python, Typst CLI/fallback + pinned version, fonts, output dir, DB, .env, API keys, render smoke test)
- P0.5: VM install: idempotent scripts/setup_vm.sh (apt, uv, Python 3.12, typst 0.14.2, fonts, uv sync, .env, doctor), scripts/update.sh, docs/INSTALL_VM.md (Vietnamese)
- P1.1: word search: generator (directions by level/audience, masks, decoys, filler repair for blocked words + accidental duplicates), independent solver/verify, difficulty score, Typst render + solution highlights, hidden_message constraint, 21 built-in theme lists, `forge puzzle`
- P1.2: sudoku 4x4/6x6/9x9: seeded generator (rot-180 symmetry), technique-guided clue removal, independent python solver + rustoku cross-check, technique-based grading (rustoku solve_steps), render, shaded_cells constraint; `forge puzzle -o key=value`
- P1.3: maze: growing-tree generator (river factor by level), perfect-maze verification (tree check + BFS route), difficulty, SVG render + solution route, path_letters constraint with decoys
- P1.4: word scramble (unique anagrams vs ENABLE + word bank, answer_is bonus word) and cryptogram (PD quotes, derangement cipher, dictionary-pattern solver over SCOWL-35, greedy hints until unique, answer_is); bundled ENABLE (PD) + SCOWL-35 (permissive) word lists
- P1.5: crossword (own code, no GPL): criss-cross builder from theme words, slots/numbering, fill-in solver with starter letters until unique, clue mode (numbered Across/Down from options.clues), render
- P1.6: book builder: planner (progressive/mixed/by_section, weighted types, theme rotation), generation with seed retries + registry dedupe, front matter (title, copyright, how to play, TOC with real pages), puzzle pages, N-up solutions, back matter, manifest.json + puzzles.jsonl, `forge book build/verify`; example_mixed + example_sudoku_large_print specs
- PQ.1: QA framework: check registry (stable ids, BLOCKER/MAJOR/MINOR, findings with evidence, exceptions = fail), scoring (0 BLOCKER + 0 MAJOR), MINOR-only hash-bound waivers, sha256 hash lock, book state machine with history, gate runner with auto-fix rounds + stale-report invalidation
- PQ.2: QA L1: second solvers with different algorithms for all 6 types (forge/qa/solvers2.py), checks dual_solver/unique/rules/difficulty_band/kid_safety/catalog_unique; builder picks seeds in the exact difficulty band, planner caps unreachable levels (manifest requested_level); cryptogram length-based levels + 20 long PD quotes
- PQ.3: QA L2 on the rendered PDF (pypdfium2): trim, safe area vs KDP minimums, fonts embedded, min text/cell sizes by audience, image DPI, page numbers, puzzle↔solution match, instructions, blank pages, page-count overflow, thumbnails; L1.print_roundtrip (PDF text vs verified data, maze SVG byte check); fixes found by the gate: large-print header in margin, cryptogram/maze label sizes, large-print crossword cells
