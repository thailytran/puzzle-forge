# Changelog

- docs: initial project plan (CLAUDE.md, SPEC, MYSTERY_DESIGN, ROADMAP, PROMPTS)
- P0.1: scaffold (uv project, typer CLI `forge`, ruff/mypy/pytest, .env.example, .gitignore, GitHub Actions CI)
- P0.2: core models (PuzzleSpec, Puzzle, constraints, DifficultyScore, VerifyReport, PuzzleType protocol), BookSpec YAML loader, seed utils, canonical hashing
- P0.3: SQLite registry (content_hash dedupe across books, list by book, `forge registry stats|list`), settings from .env
