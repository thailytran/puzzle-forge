# Changelog

- docs: initial project plan (CLAUDE.md, SPEC, MYSTERY_DESIGN, ROADMAP, PROMPTS)
- P0.1: scaffold (uv project, typer CLI `forge`, ruff/mypy/pytest, .env.example, .gitignore, GitHub Actions CI)
- P0.2: core models (PuzzleSpec, Puzzle, constraints, DifficultyScore, VerifyReport, PuzzleType protocol), BookSpec YAML loader, seed utils, canonical hashing
- P0.3: SQLite registry (content_hash dedupe across books, list by book, `forge registry stats|list`), settings from .env
- P0.4: Typst pipeline: templates/typst/book.typ, KDP trim/margin table (configs/kdp.yaml), even page padding, OFL fonts in assets/fonts, `forge layout demo`; CLI backend with python-package fallback
- P0.6: `forge doctor` (Python, Typst CLI/fallback + pinned version, fonts, output dir, DB, .env, API keys, render smoke test)
- P0.5: VM install: idempotent scripts/setup_vm.sh (apt, uv, Python 3.12, typst 0.14.2, fonts, uv sync, .env, doctor), scripts/update.sh, docs/INSTALL_VM.md (Vietnamese)
- P1.1: word search: generator (directions by level/audience, masks, decoys, filler repair for blocked words + accidental duplicates), independent solver/verify, difficulty score, Typst render + solution highlights, hidden_message constraint, 21 built-in theme lists, `forge puzzle`
