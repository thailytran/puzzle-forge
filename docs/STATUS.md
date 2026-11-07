# STATUS

- Current phase: P1 milestone
- Current task: **P1.8 — waiting for owner review** (`review/P1.8.md`, regenerated after feedback: cryptogram 5-10 quotes/page, scramble 20 words/page)
- What works: 6 puzzle types; `forge book build`; QA gate L1–L3 (`forge qa run`, auto-fix, HTML report,
  hash lock, states); `forge sku assign` (Product Hub / dev); `forge review-pack`; 3 sample books QA_PASSED.
- Known issues: crosswords are fill-in until AI clues (P2.3); `themes: auto` rotates all built-in themes
  until AI sub-themes (P2.4); proofread is dictionary-only until P2; cryptograms need ~5 given letters for
  provable uniqueness.
- Editions: digital (Letter/A4) + spiral (colour/gray, duplex/simplex, bleed) with watermark, stamp/trace done; review/PE.md waiting; brand is a placeholder.
- Blueprints: escape_adult + preview done (PB.1); colour-by-number level 1 done (PB.2); review/PB.md waiting.
- Next (PB): PB.3 page planner, PB.4 art requests + compositor, PB.5 escape sample ≥ 50 pages (needs P3 case data).
- Then: owner approval of brand + review/PE.md + the content-rules table + LLM key decision → PC.1/PC.2/PC.5 → P2.1 + PC.4 → PC.6 (P1.8-v2).

## Coverage of the "QA gate + SKU/Marketing + references" request (2026-11-07)

| Item | State |
|---|---|
| Step 0 licenses, notices, REFERENCES (env-zebra, escaperoom, AymanJabr, Artefactum original) | done |
| Step 1 QA_SPEC + golden rule 9 | done |
| QA state machine + history, hash lock, scoring, waivers | done (PQ.1) |
| L1 per puzzle (dual solver, unique, rules, band, kid safety, catalog, print round-trip) | done (PQ.2/PQ.3) |
| L2 per page | done (PQ.3) |
| L3 whole book (+ dictionary proofread) | done (PQ.4); AI proofread → P2 |
| Report json/html, `forge review` | done (PQ.5) |
| Auto-fix N rounds | done (classic books) |
| L4 mystery logic, reader_sim, case uniqueness, playtest | spec done; code in P3.8–P3.10 |
| L5 metadata/marketing text | spec done; code in P4.5 |
| SKU (Portal format, Hub shared counter, Dev provider, age codes) | done (P4.4) |
| book_card.json | spec done; code in P4.5 |
| marketing_brief.json + `forge marketing prompt` | spec done; code in P4.6 |
| Steps 2–5 mystery pipeline S1–S10, causal graph, logic grid, reader sim, export-play | design done (MYSTERY_DESIGN §5, §9–§13); code in P3.1–P3.10 |
| Step 6 ROADMAP (PQ, P3 detail, P4.4–4.6), tests listed | done; logicgrid/causal/reader_sim tests come with P3 |
| Ports & adapters + INTEGRATION_HALOSPARK.md + P7 | done (design + SKU port); rest in P7 |
