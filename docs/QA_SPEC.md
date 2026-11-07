# QA SPEC — the gate every book must pass

Golden rule 9: **no book reaches a human reviewer unless QA passes 100 % of mandatory checks.**

## 1. Book state machine (SQLite, with history)

```
DRAFT ──► QA_RUNNING ──► QA_PASSED ──► SKU_ASSIGNED ──► METADATA_READY ──► MANUAL_REVIEW ──► APPROVED ──► MARKETING_READY
             │   ▲                                                            │
             ▼   │ auto-fix (regenerate failing puzzles/pages, ≤ N rounds)    ▼
          QA_FAILED ─────────────────────────────── (N exhausted) ──► stays QA_FAILED (human needed)
                                                                    REJECTED (+ comments) ──► DRAFT
```

- Table `book_states(book_id, state, at, actor, note)` (append-only history) + `books(book_id, state, ...)`.
- Illegal transitions raise; every transition records actor + note.
- Auto-fix loop: on `QA_FAILED`, failing puzzles are regenerated with the next derived seed
  (`derive_seed(seed, "fix", round)`), affected pages re-laid out, QA re-run. `N = qa.max_fix_rounds`
  (default 3). Never hand-edit output.
- **Hash lock**: a QA report stores `sha256` of `interior.pdf`, `cover.pdf` (when present) and
  `manifest.json`. Any state after `QA_PASSED` is valid only while the hashes match; on mismatch the
  book drops back to `DRAFT` and QA must re-run (`forge book status` shows "stale").

## 2. Scoring

Every check result: `{id, level: BLOCKER|MAJOR|MINOR, status: pass|fail|skip, evidence: {page,
puzzle_id, measured, expected, ...}, message}`.

**PASS (100 %) = 0 BLOCKER fails and 0 MAJOR fails.** MINOR fails are listed and allowed only with a
manual waiver (`forge qa waive <book_id> <check_id> --reason ...`, stored with the report hash).
`skip` is allowed only when the check does not apply (e.g. L4 on a classic book) — a mandatory check
that cannot run (missing tool) is a **fail**, never a skip. No averages, no partial pass.

## 3. Check catalog

IDs are stable; the registry lives in `forge/qa/checks.py`.

### L1 — every puzzle (BLOCKER unless noted)
| ID | Check |
|---|---|
| L1.dual_solver | Re-solve with a solver using a different algorithm from the generator; result == stored solution. |
| L1.unique | Exactly one solution where the type requires it (sudoku, logic grid, crossword fill-in, cryptogram (dictionary proof), scramble, maze route). |
| L1.rules | Type rules. Sudoku: rows/cols/boxes. Word search: every word found exactly once, no blocklisted word anywhere in the grid. Maze: exactly one route, entrance/exit open. Crossword: entries in dictionary/word bank, clue contains neither answer nor same-stem word. Cryptogram: derangement + unique decoding. Logic grid: two solvers agree on one solution. |
| L1.difficulty_band | Measured difficulty label within the declared level (MAJOR; ±0 bands for adult, kids may sit one band lower). The planner caps levels a type/audience cannot honestly reach (scramble, cryptogram ≤ hard; kids 6–8 and large-print crossword ≤ medium) and records `requested_level` in the manifest; the builder tries up to 30 seeds per puzzle for an exact band. |
| L1.kid_safety | Blocklist (+ LLM check from P2) on all words/clues/text of kids' books. |
| L1.catalog_unique | `content_hash` not used by any other book in the registry. |
| L1.print_roundtrip (PQ.3) | "Printed = verified": extract the puzzle back from the rendered PDF (text layer per grid/list) and compare with the verified data — must match 100 %. |

### L2 — every page
| ID | Level | Check |
|---|---|---|
| L2.trim | BLOCKER | MediaBox == trim size of the spec (±0.5 pt). |
| L2.safe_area | BLOCKER | All text/graphics inside the margins (gutter by page count); nothing clipped or overflowing. |
| L2.fonts_embedded | BLOCKER | Every font embedded (subset ok). |
| L2.min_sizes | MAJOR | Min font size / cell size by audience (kids_6_8 cell ≥ 0.45", large print text ≥ 16 pt, grid ≥ 0.4"). |
| L2.image_dpi | BLOCKER | Raster images ≥ 300 effective DPI. |
| L2.page_numbers | MAJOR | Printed page numbers continuous. |
| L2.solution_match | BLOCKER | Puzzle #n page and solution #n reference the same `puzzle_id`. |
| L2.instructions | MAJOR | Each puzzle type has a "how to play" page or intro line. |
| L2.no_unintended_blank | MAJOR | No blank page except declared `notes`/`blank` pages. |
| L2.thumbnails | MINOR | PNG thumbnail of every page exported (`previews/`). |
| L2.page_count_match | BLOCKER | PDF page count == planned layout (nothing overflowed onto extra pages). |

Implementation notes: pages are rasterized at 72 dpi with pypdfium2; "ink" = gray < 200. Safe area uses the
KDP minimums (0.25" + gutter by page count; recto pages have the gutter on the left). Running headers/footers
(top/bottom 0.5") are exempt from minimum text sizes; solutions/title/notes pages are exempt from size checks.
L1.print_roundtrip compares whitespace-free page text with the verified data (grid letters in reading order,
givens, word lists, scrambles; cipher letters as an ordered subsequence) and re-renders maze SVGs byte-for-byte.

### L2 — editions & watermark (owner rules 2026-11-07)
| ID | Level | Check |
|---|---|---|
| L2.watermark_knockout | BLOCKER | No watermark ink inside any functional block (render with vs. without watermark: functional areas identical). |
| L2.watermark_contrast | MAJOR | Watermark lightness change outside functional areas ≤ threshold (colour ≤ 5 %, gray ≤ 4 % darkening); grayscale editions have no dark gray patches. |
| L2.binding_margin | BLOCKER | Spiral: no ink within the binding-edge margin (0.75" default), correct side per page (duplex alternates). |
| L2.bleed_marks | MAJOR | When bleed is on: page = trim + 2 × 0.125", crop marks at the trim corners outside the trim box. |
| L2.stamp_diff | BLOCKER | A stamped copy differs from its QA'd master only inside the approved stamp zones (footer band, micro-pattern strip) + metadata; anything else changed = fail. |

### L3 — sections / whole book
| ID | Level | Check |
|---|---|---|
| L3.counts | BLOCKER | Page count and puzzle count match the spec; total pages even and within KDP min/max. |
| L3.distribution | MAJOR | Type mix and difficulty curve match the mode (progressive non-decreasing by section, mixed per section of 10). |
| L3.toc | BLOCKER | Table-of-contents page numbers == real page numbers. |
| L3.matter | MAJOR | Required front/back matter present, including copyright page. |
| L3.proofread | MAJOR | Spelling (dictionary) + grammar (AI proofread from P2) over all text. |
| L3.placeholders | BLOCKER | No "TODO", "TBD", "Lorem", `{...}` templates, "XXX". |
| L3.richness_counts | MAJOR | Words / quotes / grids per page ≥ the level minimum (`configs/content_rules.yaml`); cryptogram cipher letters per page ≥ minimum. |
| L3.ws_coverage | MAJOR | Word search: cells belonging to real words / all cells ≥ level threshold (kids ≥ 45–50 %, adult ≥ 40 %, expert ≥ 35 %). |
| L3.page_fill | MAJOR | Body ink bounding box ≥ 65 % of the printable area on puzzle pages (no half-empty pages), with font minimums still met (L2.min_sizes). |
| L3.diversity | MAJOR | No word used more than 2× in the book; every puzzle page has its own sub-theme (content plan). |
| L3.theme_relevance | MAJOR | AI scores each word / quote / illustration description against the page sub-theme (≥ 0.7); off-topic items are replaced. Needs the AI layer: without it the check fails (a mandatory check that cannot run is a fail). |
| L3.age_fit | MAJOR | Kids: common words (SCOWL ≤ 20), length within the level range; Expert: average word length ≥ 7 and not all common words. |

### L4 — mystery / secret-discovery logic
| ID | Level | Check |
|---|---|---|
| L4.timeline | BLOCKER | Truth timeline consistent: nobody in two places at once; culprit had opportunity; every false alibi is contradicted by at least one obtainable evidence. |
| L4.relations | MAJOR | Relationship matrix symmetric and consistent with secrets. |
| L4.graph | BLOCKER | Causal/clue graph is a DAG; every knot has ≥ 2 evidence; every node reachable; final depends on all chapter keys. |
| L4.reader_sim | BLOCKER | Reader simulation in real page order: evidence appears before the knot needing it; solver → token → encoder → page number lands on the right page; dead-end pages return correctly; no orphan pages; meta-puzzle solves to `final_answer`. |
| L4.case_unique | BLOCKER | Suspects × attributes modelled as constraints from evidence the reader has: both solvers find exactly one culprit; red herrings do not create a second solution. |
| L4.spoilers | MAJOR | Chapter k reveals no fact first available after k (string match + AI check). |
| L4.solution_text | MAJOR | Solution/explanation text agrees with solver output. |
| L4.playtest | MAJOR | Two independent agents of different models (Claude + GPT), no answers, on the play-test export: (a) solve the case; (b) cannot name the culprit before the last chapter. Stuck points recorded. |

### L5 — metadata & marketing text
| ID | Level | Check |
|---|---|---|
| L5.kdp_limits | BLOCKER | Title + subtitle ≤ 200 chars combined; description ≤ 4000 chars, allowed HTML subset only; 7 keywords each ≤ 50 chars. |
| L5.claims | BLOCKER | No third-party trademarks, no forbidden claims ("bestseller", "#1", "free", "award-winning", competitor names). |
| L5.facts | BLOCKER | Description matches reality: page count, puzzle count, ages, puzzle types, large print, solutions included. |
| L5.no_spoilers | BLOCKER | Hooks / teaser / listing never reveal culprit or `final_answer`. |
| L5.names | MAJOR | Character names identical across book, hooks, book_card and listing. |

## 4. Report

`output/<book_id>/qa/qa_report.json` + `qa_report.html` (per-page thumbnails, every check with status,
evidence and links to the failing page/puzzle). `qa_report.json` header:
`{book_id, run_id, started, finished, result: PASSED|FAILED, hashes: {interior, cover, manifest},
counts: {blocker_fail, major_fail, minor_fail, waived}, checks: [...]}`.

Reviewers only see books in `QA_PASSED`. Before the web UI (P5): `forge review <book_id>
--approve|--reject --note "..."` (moves `MANUAL_REVIEW → APPROVED|REJECTED`).

## 5. After QA_PASSED: SKU + book card

- **SKU** (Portal standard, from halospark-suite Product Hub):
  `BRAND-AUD-LINE-FMT-NNNN-SGL` or `BRAND-AUD-LINE-FMT-NNNN-SERnnn-vv`, e.g.
  `HSP-ADULT-PZL-PBK-0007-SGL`. Codes and the audience mapping live in `configs/sku.yaml`.
  Source: Product Hub shared counter via `SkuPort` → `HubSkuProvider` (`POST api/products`,
  `X-Hub-Token`). `DevSkuProvider` exists for tests only and prefixes every SKU with `DEV-`.
  Age codes: KID1/KID4/KID9/TEEN/ADULT/SENIOR (docs/INTEGRATION_HALOSPARK.md §3).
- **book_card.json** (AI-written text, code-filled facts): `sku, series_name, volume, title, subtitle,
  pen_name, tagline, hooks[3–5], short_description (2–3 sentences), long_description (KDP HTML subset),
  case_teaser (no spoilers), characters[{name, role, look}], setting, tone, audience/ages,
  puzzle_types{type: count}, difficulty_mix, page_count, trim_size, interior (bw|color), paper,
  cover_finish, resolution_dpi: 300, spine_width_in (KDP formula by paper + pages), keywords[7],
  categories[2–3], sample_pages[{page, png, solution_png}]` (best pages at 300 DPI + solutions).
  Must pass L5 → `METADATA_READY`.

## 6. Marketing handoff

- `marketing_brief.json` = book_card + sample pages + cover, in the Portal schema used for
  Coloring Page listings, so the Portal can ask OpenAI for a Gemini master prompt.
  Fallback: `forge marketing prompt <book_id>` calls OpenAI with the same structure.
- Image set: cover mockup, "Look Inside" (2–3 real pages), "What's inside", difficulty / large-print
  badge, "Solutions included", character/case teaser, gift-context scene.
- **Rule**: Gemini draws only backgrounds, scenes, mockups and characters. Real puzzle pages and every
  word or number on an image are composited by code from QA'd files. AI never redraws a puzzle grid.
