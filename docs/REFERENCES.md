# References

How external projects influence Puzzle Forge. Rule: MIT/BSD/Apache code may be reused with its
license in `licenses/` and a header in the adapted file; no-license or GPL sources are **ideas only**
(fully re-implemented, nothing copied). Checked on 2026-11-07.

## 1. GeneralReasoning/env-zebra — logic grid (zebra) generator
- **License**: README states "MIT", but the repository contains **no LICENSE file** and no copyright
  line. Treated as **ideas only**: we write our own code (no copied lines), credited here.
- **Learned**: (1) generate a random solution first, then a large pool of candidate clues from it;
  (2) clue kinds: same-house, not-same-house, neighbor, left-of, immediately-left, position;
  (3) keep adding clues until a domain-propagation solver with backtracking counts exactly one
  solution, then **prune** clues one by one while the solution stays unique; (4) difficulty = grid
  size (3x3 → 8x7) plus clue mix; (5) clue signature dedupe; (6) fully seed-deterministic.
- **Reused**: ideas (1)–(6). Our solver 1 is propagation + backtracking (own code); solver 2 is a
  brute-force permutation search for small grids / OR-Tools CP-SAT (Apache-2.0) for large ones.
- **Affects**: `forge/puzzles/logicgrid/*`, the case-uniqueness check in `forge/qa/l4_mystery.py`.

## 2. csurfer/escaperoom — virtual escape room from a JSON campaign
- **License**: MIT © 2021 Vishwas B Sharma → `licenses/escaperoom.txt`.
- **Learned**: a minimal, validated campaign schema: `story {title, text, images}` +
  `puzzles [{title, text, images, hints, answer}]`, played in order; the right answer unlocks the
  next puzzle; JSON-schema validation before hosting.
- **Reused**: the schema *shape* for our `mystery_book.json` export and an escaperoom-compatible
  export (`forge mystery export-play --format escaperoom`). We do not vendor its server; our default
  play-test output is a self-contained static HTML page we write ourselves.
- **Affects**: `forge/mystery/export_play.py`, `docs/MYSTERY_DESIGN.md` §9.

## 3. AymanJabr/Escape-the-room-AI-stats-game — LLM escape room with a causal graph
- **License**: none → **ideas only**.
- **Learned**: `graph.json` of nodes with **requires/unlocks**; the backend filters the game state so
  agents only see currently available nodes (no spoilers of future content); NPC personas change by
  "stat tier", i.e. characters reveal more only when conditions are met; LLM agents (classifier,
  game master, NPC) never own the state — code does.
- **Reused**: the requires/unlocks causal graph, state filtering, and **reveal rules** for characters
  (interrogation pages) — re-implemented in `forge/mystery/causal_graph.py`.
- **Affects**: `forge/mystery/causal_graph.py`, `forge/qa/reader_sim.py`, interrogation documents (S8).

## 4. Artefactum — mystery game generator (blog, dominatedbycline.github.io)
- **License**: blog post (no code reused). The host was not reachable from the build session, so
  the design follows the owner's summary.
- **Learned**: generate in a fixed order where each stage is grounded in the previous one:
  brief → characters → relationships → **truth timeline** → story arc → clues → prose; validate
  each stage before moving on; narration may only use established facts ("grounded").
- **Reused**: stage order S1–S10 with validation + editable YAML between stages.
- **Affects**: `forge/mystery/stages/*`, `docs/MYSTERY_DESIGN.md` §5.

## 5. thailytran/halospark-suite — Portal / Product Hub (owner's own project)
- **Learned**: SKU format `BRAND-AUD-LINE-FMT-NNNN-SGL` (single) or `...-NNNN-SERnnn-vv` (series),
  counter per prefix (Product Hub `next_sku`), codes from Hub settings (`HSP`, `ADU/KID/TEE/...`,
  line `PZL` = "Puzzle / game book", format `PBK` = printed book). Hub endpoints
  `POST api/products`, `POST api/products/{sku}/produced {title, book_json, listing_copy}`.
  Coloring Studio marketing v3: ChatGPT writes layout/style ideas, Gemini draws graphics,
  **Python places exact content** (real pages, text that must be exact).
- **Reused**: SKU format (`configs/sku.yaml`), marketing rule "AI draws background only, code places
  real pages and every number", Hub handoff fields.
- **Affects**: `forge/publish/sku.py`, `forge/publish/book_card.py`, `forge/publish/marketing.py`.
