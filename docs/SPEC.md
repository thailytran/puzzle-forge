# SPEC — Puzzle Forge technical specification

## 1. Data models (pydantic v2)

```python
Level = Literal["very_easy", "easy", "medium", "hard", "expert"]
Audience = Literal["kids_6_8", "kids_9_12", "teen", "adult", "senior_large_print"]

class PuzzleSpec(BaseModel):
    type: str                      # "wordsearch" | "crossword" | "sudoku" | "maze" | ...
    level: Level
    audience: Audience
    theme: str | None = None       # "ocean animals"
    words: list[str] | None = None # explicit word list (else from wordlists / AI)
    size: tuple[int, int] | None = None
    options: dict[str, Any] = {}   # type-specific (directions, mask shape, symmetry...)
    constraints: list[Constraint] = []   # mystery: force a token (see §5)

class Puzzle(BaseModel):
    id: str                        # deterministic: "<type>-<content_hash[:16]>" (not a ULID, see golden rule 3)
    type: str
    spec: PuzzleSpec
    seed: int
    data: dict                     # type-specific puzzle payload (grid, clues, walls, ...)
    solution: dict                 # type-specific solution payload
    token: str | None = None       # mystery: what this puzzle "yields" (e.g. "HARBOR", "47")
    content_hash: str              # sha256 of canonical(data)
    difficulty: DifficultyScore | None = None
    verify: VerifyReport | None = None

class DifficultyScore(BaseModel):
    score: float                   # 0..100
    label: Level
    features: dict[str, float]     # what drove the score (for tuning)

class VerifyReport(BaseModel):
    ok: bool
    unique: bool | None
    solver: str
    messages: list[str] = []
```

## 2. Book spec (YAML) — classic book

```yaml
# configs/books/example_wordsearch.yaml
book:
  title: "Ocean Adventures Word Search"
  subtitle: "100 Fun Puzzles for Kids Ages 6-8"
  author: "Pen Name"
  audience: kids_6_8
  trim: "8.5x11"            # 8.5x11 | 8x10 | 6x9 | 8.5x8.5
  large_print: false
  interior: bw              # bw | color
  content_pages: 100        # puzzle pages (front matter + solutions are extra)
  seed: 20261106
puzzles:
  mode: progressive         # progressive | mixed | by_section
  distribution: { easy: 30, medium: 40, hard: 30 }
  types:
    - { type: wordsearch, weight: 1.0, options: { directions: auto_by_level } }
  themes: auto              # auto = AI picks 100 sub-themes from book theme; or explicit list
  theme: "ocean"
front_matter: [title, copyright, how_to_play, table_of_contents]
back_matter:  [solutions, about, thank_you]
solutions: { per_page: 6 }
```

Mixed books: list several `types` with weights; `mode: mixed` interleaves types and levels per section of 10.

## 3. Difficulty model per type (first version, tune later)

| Type | Easy | Medium | Hard | Signals for score |
|---|---|---|---|---|
| Word search | 10x10–12x12, 8–12 words, E/S only | 14x14, 15–20 words, + diagonals | 17x17–20x20, 25–30 words, all 8 dirs, backwards, shared letters, decoy partials | grid area, #dirs, backwards ratio, overlap ratio, decoy count |
| Sudoku | 36–45 givens, singles only | naked/hidden pairs | X-wing, chains | human-technique trace from rustoku |
| Maze | 10x10 cells | 20x20 | 35x35+, low river factor | solution length, dead-end count, branching |
| Crossword | 9x9 mini, easy common words | 13x13 | 15x15, wordplay clues | grid size, word frequency rank, clue style |
| Cryptogram | short quote, 3 letters given | 1 letter given | none given, rare letters | length, letter-pattern ambiguity |
| Logic grid | 3x3 | 4x4 | 5x5–6x6 | #constraints, required strategies, search depth |
| Scramble | 4–5 letters | 6–7 | 8+ | length, anagram ambiguity (must be unique!) |

Kids (6–8): levels `very_easy` → `medium` at most (owner decision 2026-11-07), bigger cells (≥ 0.45"),
uppercase, no backwards words. Senior large print: font ≥ 16pt, cell ≥ 0.4", fewer puzzles per page;
large-print crosswords at most `medium` (grid ≤ 13×13). Scramble and cryptogram at most `hard`.
Levels above a cap are lowered by the planner and recorded as `requested_level` in the manifest.

Reader-facing labels (books, listings): very_easy = **Beginner**, easy = **Easy**, medium =
**Intermediate**, hard = **Hard**, expert = **Expert** (`forge.core.models.LEVEL_LABELS`).

## 4. Layout

- Typst templates in `templates/typst/`: `book.typ` (page setup, running header, page numbers),
  `puzzle_page.typ`, `solution_grid.typ`, `front_matter.typ`, `mystery_chapter.typ`, `evidence_board.typ`.
- Python builds a `layout.json` (ordered pages with blocks), then calls `typst compile book.typ --input ...`.
- Trim sizes and margins come from `forge/layout/trim.py`. **No bleed** for standard interiors.
  Gutter (inside) margin depends on page count — store KDP's table in config and **re-check against the
  current KDP help page before release**. Outside/top/bottom ≥ 0.25"; use 0.5" for comfort.
- Page count must be **even**; pad with "Notes" / "Doodle" pages.
- Fonts: bundle OFL fonts in `assets/fonts/` (e.g. Atkinson Hyperlegible for large print, a clean
  sans for grids, a serif for mystery prose, a typewriter face for case files).
- Preflight (part of QA L2, `forge/qa/`): page size, all fonts embedded, no content inside margins, images
  ≥ 300 DPI, even page count, PDF/X-friendly (no transparency issues).

## 5. Constraints for mystery puzzles (answer → token)

| Constraint | Applies to | Meaning |
|---|---|---|
| `hidden_message(text)` | wordsearch | unused letters, read row by row, spell `text` |
| `shaded_cells(cells, expect)` | sudoku, crossword, kakuro | values in given cells read `expect` |
| `path_letters(seq)` | maze | letters placed on the solution path spell `seq`; decoy letters off-path |
| `answer_is(word)` | scramble, cryptogram, riddle | final answer equals `word` |
| `grid_solution(facts)` | logicgrid | solution must match given who/where/what facts |
| `page_number(n)` | any | token is converted to a page number the reader turns to |

Generators should try up to N seeds to satisfy constraints, then verify. Fail loudly if impossible.

## 6. AI layer (`forge/ai/`)

- `LLMClient` interface: `complete_json(prompt_id, variables, schema) -> dict`.
- Prompts live in `forge/ai/prompts/*.md` with front-matter (model, temperature, max_tokens, schema).
- Every response is validated by pydantic; on failure → retry with the error message (max 2), then fail.
- Cache by `(prompt_id, variables, model)` hash in SQLite → re-runs are free and deterministic.
- Track tokens + cost per book in `manifest.json`.
- Tasks: `theme_ideas`, `word_list`, `crossword_clues`, `kid_safety_check`, `case_bible`, `clue_graph`,
  `chapter_prose`, `solution_explanation`, `listing_copy`, `playtest_reader`.

## 7. CLI

```
forge puzzle <type> [--level] [--theme] [--seed] [--out]     # one puzzle -> png/pdf preview + json
forge wordlist build --theme "ocean" --audience kids_6_8      # AI expand + filter + save
forge book build <spec.yaml>                                  # full classic book
forge book verify <output_dir>                                # re-verify all puzzles + preflight
forge mystery new --template lighthouse --audience adult      # create case bible draft
forge mystery build <case.yaml>                               # full mystery book
forge mystery playtest <output_dir>                           # AI reader playtest report
forge series new / forge series next                          # series bible + next volume
forge qa run <output_dir>                                     # QA gate L1–L5 (docs/QA_SPEC.md)
forge book status <book_id>                                   # state machine + hash-lock validity
forge review <book_id> --approve|--reject --note "..."        # manual review (before the web UI)
forge mystery build <case.yaml> [--from-stage S4]             # staged pipeline S1–S10
forge mystery export-play <book_id> [--format html|escaperoom]
forge sku assign <book_id> / forge book card <book_id>        # after QA_PASSED
forge marketing prompt <book_id>                              # OpenAI master prompt (fallback)
forge serve                                                   # web UI + API (later)
```

## 8. Output package

```
output/<book_id>/
  interior.pdf  cover.pdf  listing.json  manifest.json  book_card.json  marketing_brief.json
  qa/qa_report.json  qa/qa_report.html  previews/*.png  stages/S*.yaml (mystery)  mystery_book.json
```

## 9. QA gate, SKU, marketing

See `docs/QA_SPEC.md` (golden rule 9): state machine DRAFT → … → MARKETING_READY, check catalog
L1–L5 (BLOCKER/MAJOR/MINOR), hash-locked reports, SKU in the Portal format, book_card, marketing brief.
