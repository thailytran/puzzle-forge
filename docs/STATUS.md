# STATUS

- Current phase: P9 Adventure line (owner 2026-11-23: "làm P9.1–P9.5 Adventure"); P8 CBN Mystery and the P10.8 milestone still open
- Current task: P9.5 milestone — "The Snow Queen's Library" needs Studio art (vignettes, search scenes, icon sheets), the Gemini self-check and the owner's ticks, then `forge adventure build --art` and review
- What works (P9): `forge adventure check|build|studio|merge`; frame check + logic lock + reader run (EVERGLOW from 8 keys); verified puzzles A/B per chapter; composed story / search / answer-key / lock pages; 71-page layout with every story on a left page facing its search page (48 chapter pages)
- Known issues (P9): the Typst page types `fullpage` / `adv_story` were written without a Typst backend in the cloud session — first render on the owner machine must be checked; Puzzle B slots can be found by elimination once 7 keys are known (inherent to an 8-slot lock; letters stay necessary); the Studio tab is not built yet (halospark-suite repo); puzzle pages use the plain layout (no designed panels yet)
- Next: Studio Adventure tab (halospark-suite) → art for book 1 → P9.5 review pack

## P8 / earlier

- Current phase: P8 (CBN Mystery line, owner priority 2026-11-18); P10.8 milestone still waits for the owner
- Current task: P8.3e picture mosaics from Gemini art (owner: 13x13 icons are too plain), then P8.3d crossword / logic grid side puzzles, P8.3f spiral + portrait finale; P8.4 sample book after that
- What works: P10.1-P10.7; P8.1b cell shapes (square, hex, triangle, circle); P8.2 blueprint cbn_mystery; P8.3 case builder + `forge mystery check|build` (sample "The Vanished Star": 56 pages, 24 puzzle pages); P8.3b picture reveals + trait keywords + logic lock (dual solver, small hints, dead-end decoys, leak check, causal graph, reader simulation). 13x13 pictures fit square / hex / circle cells for adults and square / circle for kids (triangles keep letters and symbols)
- Known issues: the case book is laid out with the generic page template (blueprint zones and art are not composited yet); solutions list side-puzzle keywords only; QA gate is not wired to `forge mystery build`; 8 necessary clues need at least 9 suspects; 8 mm triangles (kids) and 3-character codes in hex / triangle do not fit
- P8.3g done (Studio art placed by `forge mystery build --art`); to verify on the VM: `uv run pytest -q tests/mystery` + a rendered book with the Studio art package
- Next: P8.4 (QA + review pack, kids edition), HALOSPARK Studio adapter (case_bible via ChatGPT, art via Gemini)
