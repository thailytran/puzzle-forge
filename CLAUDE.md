# CLAUDE.md — Puzzle Forge

> Read this file fully at the start of every session. Then read `docs/ROADMAP.md` to find the current task.

## 1. What this project is

**Puzzle Forge** is a tool that produces print-ready **English-language** puzzle books for Amazon KDP:

1. **Classic puzzle books** — word search, crossword, sudoku, maze, cryptogram, word scramble, logic grid…
   ~100 content pages per book, difficulty either progressive (easy → hard) or mixed per chapter.
   Audiences: kids (6–8, 9–12), adults, seniors (large print).
2. **Mystery puzzle books** ("solve the case") — single books or series. A story (detective case, legend,
   hidden secret) is split into chapters; each solved puzzle yields a piece of evidence / key that unlocks
   the next knot of the story, until a final meta-puzzle reveals the solution.

Output per book: `interior.pdf`, `cover.pdf`, `listing.json` (title, subtitle, description, keywords, categories),
`manifest.json` (every puzzle, seed, hash, difficulty score, verification result).

Owner works mostly from a company machine through **claude.ai/code (web)** and runs the tool on a home
**Ubuntu 24.04 VM** (reachable via Tailscale). This project is **independent from HALOSPARK SUITE**; a later
phase exposes an HTTP API so HALOSPARK Studio can queue book jobs.

## 2. Golden rules (never break these)

1. **AI never decides a puzzle answer.** LLMs write words, clues, story and explanations. Every puzzle is built
   by deterministic code and then **re-solved by an independent solver**. A puzzle that fails verification is
   discarded and regenerated — never "fixed by hand" in the output.
2. **Unique solution** where the puzzle type requires it (sudoku, logic grid, crossword fill, kakuro, nonogram…).
3. **Deterministic**: every generator takes a `seed`. Same spec + same seed ⇒ byte-identical puzzle.
4. **No duplicates**: every puzzle has a canonical `content_hash`; a SQLite registry rejects duplicates across
   all books ever produced.
5. **Kid safety**: all word lists / clues / story text for kids' books pass a content filter (blocklist + LLM
   check). No violence, gore or romance in kids' mysteries ("stolen", "missing", "mystery" — never "murder").
6. **Licenses**: only MIT / BSD / Apache / Expat / OFL dependencies inside the product. **No GPL code**
   (e.g. do NOT vendor `genxword`; we write our own crossword filler). Fonts must be OFL or similar.
7. **No copied IP**: don't reuse names, characters, layouts or text from existing books (e.g. Murdle).
   Legends must be public domain.
8. **Secrets** only in `.env` (never committed). Provide `.env.example`.
9. **QA gate**: no book is handed to a human reviewer unless QA passes 100 % of mandatory checks
   (0 BLOCKER + 0 MAJOR fails; see `docs/QA_SPEC.md`). QA reports are locked to the sha256 of the
   files they checked; any change invalidates them.

## 3. Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.12, managed with `uv` |
| Models / validation | `pydantic` v2 |
| CLI | `typer` (entry point: `forge`) |
| Rendering | **Typst** (CLI binary, called from Python) → PDF; SVG for grids/mazes generated in Python |
| Sudoku | `rustoku` (generation + uniqueness + human-technique trace for difficulty) |
| Word search | `word-search-generator` (MIT) wrapped behind our interface, or own implementation |
| Maze | `mazelib` (MIT) or own implementation; render to SVG ourselves |
| Logic grid | own generator + constraint solver (reference: GeneralReasoning/env-zebra, MIT) |
| Crossword | **own** filler + solver (no GPL) |
| LLM | provider abstraction `forge/ai/` — Anthropic (default) + OpenAI; JSON-schema structured output |
| Storage | SQLite (`data/forge.db`) for registry/jobs; files under `output/<book_id>/` |
| Web (later) | FastAPI + simple HTML UI (must work from a browser only) |
| Tests | `pytest`, `hypothesis` for property tests |
| Lint/format | `ruff`, `ruff format`, `mypy --strict` on `forge/core` and `forge/puzzles` |

## 4. Repo layout (target)

```
forge/
  core/          # models (Puzzle, BookSpec, ...), seeds, hashing, registry, difficulty
  puzzles/       # one sub-package per type: generator.py, solver.py, render.py, difficulty.py
    wordsearch/ crossword/ sudoku/ maze/ cryptogram/ scramble/ logicgrid/ ...
  wordlists/     # theme word lists + age filters (+ LLM expansion)
  ai/            # llm client, prompts/*.md, schemas, cost tracking, cache
  mystery/       # case bible, clue graph, encoders (answer -> token), chapter planner, writer, playtest
  layout/        # typst templates, page planner, trim sizes, answer key, front matter
  qa/            # QA gate: check registry, L1–L5, state machine, reader_sim, report (docs/QA_SPEC.md)
  publish/       # cover, SKU, book_card, listing.json, marketing brief, export package
  ports/         # interfaces to the outside (registry, state, SKU, research, listing, notify)
  adapters/      # port implementations: standalone now, HALOSPARK SUITE later (INTEGRATION_HALOSPARK.md)
  api/           # FastAPI (later phase)
  cli.py
templates/typst/ # .typ templates
configs/books/   # example book YAML specs
data/            # sqlite db, caches (gitignored except seeds/fixtures)
output/          # generated books (gitignored)
tests/
docs/            # SPEC.md, MYSTERY_DESIGN.md, QA_SPEC.md, REFERENCES.md, ROADMAP.md, PROMPTS.md
licenses/        # third-party license texts (see THIRD_PARTY_NOTICES.md)
```

## 5. Core interfaces (summary — full spec in `docs/SPEC.md`)

Every puzzle type implements:

```python
class PuzzleType(Protocol):
    name: str
    def generate(self, spec: PuzzleSpec, seed: int) -> Puzzle: ...      # build puzzle + solution
    def solve(self, puzzle: Puzzle) -> SolveResult: ...                 # independent solver
    def verify(self, puzzle: Puzzle) -> VerifyReport: ...               # solve + compare + uniqueness
    def difficulty(self, puzzle: Puzzle) -> DifficultyScore: ...        # 0–100 + label
    def render(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock:  # typst/svg for puzzle page
    def render_solution(self, puzzle: Puzzle, ctx: RenderCtx) -> RenderedBlock: ...
```

Architecture: **ports & adapters**. Core packages never import HALOSPARK code; they talk to the outside
through `forge/ports` protocols, and only the CLI/API wires concrete adapters (see
`docs/INTEGRATION_HALOSPARK.md`).

Mystery support: generators must accept **constraints** (e.g. "the leftover letters must spell HARBOR",
"the shaded cells must read 4-7", "the maze path must pass letters K,E,Y"), so a story can force a puzzle
to produce a specific token.

## 6. Commands (keep this section up to date)

```bash
uv sync                                  # install
uv run pytest -q                         # tests
uv run ruff check . && uv run ruff format --check .
uv run forge --help
uv run forge doctor                       # machine self-check (green/yellow/red table, exit 1 on FAIL)
uv run forge registry stats                # puzzles registered per type (duplicate guard)
uv run forge registry list <book_id>
uv run forge layout demo --trim 6x9 --out output/layout_demo   # sample interior.pdf (Typst check)
uv run forge puzzle wordsearch --theme animals --level easy --seed 1 --out output/tmp
uv run forge puzzle wordsearch --theme space --level easy --audience kids_6_8 --hidden-message "LOOK UP" --shape circle
uv run forge puzzle sudoku --level hard --seed 3            # -o size=4|6|9 ; 9x9 graded by rustoku techniques
uv run forge puzzle maze --level medium --seed 4             # SVG maze; solution page shows the route
uv run forge puzzle scramble --theme ocean --level medium      # unique anagrams (ENABLE dictionary)
uv run forge puzzle cryptogram --level hard                     # PD quotes; hints added until unique
uv run forge puzzle crossword --theme ocean --level medium      # fill-in criss-cross (clue mode after P2.3)
uv run forge book build configs/books/example_wordsearch.yaml   # also example_mixed / example_sudoku_large_print
uv run forge book build <spec.yaml> --no-render                  # puzzles + manifest only
uv run forge book build <spec.yaml> --plan content_plan.yaml     # per-page sub-themes/words/quotes (edit + rebuild)
uv run forge book verify output/<book_id>
uv run forge qa run output/<book_id>              # QA gate L1-L3 (+auto-fix) -> qa/qa_report.html
uv run forge qa waive output/<book_id> <check> --reason "..."   # MINOR checks only
uv run forge book status output/<book_id>         # state, history, report valid/stale
uv run forge review output/<book_id> --approve | --reject --note "..."   # MANUAL_REVIEW only
uv run forge sku assign output/<book_id>          # QA_PASSED -> SKU from Product Hub (FORGE_SKU_PROVIDER=hub|dev)
uv run forge review-pack P1.8 output/<id1> output/<id2> ...   # milestone checklist review/P1.8.md + PNGs
uv run forge edition build output/<book_id> --edition digital --trim A4        # also 8.5x11
uv run forge edition build output/<book_id> --edition spiral [--grayscale] [--simplex] [--bleed] [--binding wire-o]
uv run forge qa run output/<book_id>/editions/<label>      # edition QA (watermark knock-out, binding, bleed)
uv run forge edition stamp <book_id> --buyer "Jane D." --order 1234 [--email x]   # per-order PDF (digital)
uv run forge edition trace <stamped.pdf>                   # read the order number back
uv run forge blueprint preview escape_adult [--trim A4]    # page types with coloured zones -> output/blueprints/
uv run forge vault init output/<book_id>                    # vault.yaml: answer type, accepted answers, listings
uv run forge vault codes output/<book_id> --count 200 [--channel print|shopify_digital]   # Book Codes CSV + code pages PDF
uv run forge vault sync [--force]                          # send queued registrations (auto-queued on APPROVED)
uv run forge vault status [<book_id>]                      # registration queue
uv run pytest -q apps/casevault/tests                      # Case Vault website tests (E2E, providers mocked)
uv run uvicorn casevault.web:app_factory --factory --reload   # run the website locally (apps/casevault/.env)
```

Typst must be installed on the machine (`typst --version`, pinned in `scripts/setup_vm.sh`). If the CLI is
missing, `forge/layout/typst_runner.py` falls back to the `typst` Python package (Apache-2.0, same compiler).
Tests that need a Typst backend are marked `@pytest.mark.typst` and skipped when neither exists; pure-Python
logic must still be fully tested. Typst always runs with `--ignore-system-fonts` + `assets/fonts/`.

## 7. How to work in this repo (autonomous step-by-step workflow)

The owner wants you to **build the project task by task without waiting** between tasks.

**Branching:** one branch per phase: `phase-p0`, `phase-p1`, … At the start of a session, run `git fetch` and
check: if `phase-pN` for the current phase exists (PR not merged yet), check it out and continue on it;
otherwise branch from `main`. Open **one PR per phase** (draft while in progress; mark ready when the
phase is complete). The owner merges.

**Loop (repeat until the session budget runs low or a STOP condition is hit):**
1. Read `docs/ROADMAP.md`; take the **first unchecked task** (or the one the user names).
2. Read the related section of `docs/SPEC.md` / `docs/MYSTERY_DESIGN.md`.
3. Write tests first for generators/solvers (including property tests: "every generated puzzle verifies").
4. Implement. Keep functions small; no network calls in tests (mock the LLM; use recorded fixtures).
5. Run `uv run pytest -q` + `uv run ruff check .` + `uv run ruff format --check .`. Fix everything.
6. Tick the task in `docs/ROADMAP.md`, update "Commands" (§6) if new commands exist, add a line to
   `docs/CHANGELOG.md`, update `docs/STATUS.md` (current task, what works, known issues, next task).
7. **Commit + push after every task** (message: `P1.2: sudoku generator, solver, difficulty`).
8. Continue with the next task.

**STOP and report (in Vietnamese) when:**
- a **Milestone** task is reached (P1.8, P3.9): the owner must review PDFs on the VM;
- a task needs something only the owner has (API keys, KDP account, a niche/style decision, money);
- the same test keeps failing after 3 honest attempts — describe the problem and options;
- the session is about to run out of context/time: finish and push the current task cleanly first.

**Report format:** what was done (task codes), how to test on the VM (exact commands), what's next,
anything the owner must decide.

**Asking the owner (rules from 2026-11-07):**
- Never send the owner to look for a file or a prompt template. Everything the owner must confirm or
  comment on is **pasted directly in the reply**: numbered questions, the recommended option for each,
  and a **pre-filled answer template** the owner only edits and sends back.
- Milestones: run `uv run forge review-pack <code> output/<book_id> ...` to create `review/<code>.md`
  (per-book checklist: pages to look at, criteria, `[ ]` boxes) plus `review/<code>/<book_id>/`
  (key-page PNGs, interior.pdf, qa_report.json); commit them so the owner can open them on GitHub or in
  Claude Code, and also paste the checklist text in the reply.
- Work lives on the session branch until the owner merges the PR: always give direct GitHub links that
  include the branch name (`/tree/<branch>/...`, `/blob/<branch>/...`).

**Where it runs:** you code in the cloud session; the owner runs the tool on a **personal Ubuntu 24.04 VM**.
You cannot reach the VM. Everything must install with `scripts/setup_vm.sh` and run with `uv run forge ...`.
Never hard-code paths of the cloud session.

## 8. Communication

- Talk to the owner in **Vietnamese**. Code, comments, docs in `docs/SPEC*`, and all **book content in English**.
- When a decision is genuinely the owner's (book niche, style, money spent on API), ask briefly; otherwise
  choose a sensible default, note it in the PR, and continue.
