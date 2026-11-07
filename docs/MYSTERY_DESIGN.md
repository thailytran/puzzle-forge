# MYSTERY DESIGN — "Solve the Case" puzzle books

## 1. Core loop

```
Story beat → Puzzle → Answer → Token (evidence / key / page number) → unlocks next Knot → ... → Final meta-puzzle → Reveal
```

- **Knot** (nút thắt): a question the reader must answer to advance ("Where did the keeper go on the last night?").
- **Evidence**: a fact earned by solving a puzzle ("The tide table shows low tide at 2:47 AM").
- Each knot needs **≥ 2 pieces of evidence**; at least one knot needs evidence from **two different chapters**
  (forces the reader to connect clues).
- The **final reveal** must be deducible only from earned evidence (fair play). No surprise facts.

## 2. Self-checking print mechanic (page jump)

Answers convert to a page number: "The code you found is the page to turn to." Correct page continues the story;
a few **dead-end pages** say "Not quite, detective…" with a gentle hint and a pointer back.
`forge/mystery/encoders.py` maps tokens → page numbers (A=1..Z=26 sums, digit codes, etc.) and the page planner
reserves those pages. For kids: simpler — "Write the secret word in the evidence box"; answer check at back.

## 3. Puzzle → evidence mechanics

| Puzzle | Yields |
|---|---|
| Word search | leftover letters spell a hidden message |
| Crossword | shaded squares spell a suspect name / password |
| Sudoku | shaded cells = safe code or page number |
| Maze | letters on the true path spell a place |
| Cryptogram | decoded letter / witness statement |
| Logic grid | who / where / when / with what (major knots) |
| Scramble / riddle | keyword |
| Map / grid coordinates | location |
| Meta-puzzle | combines the chapter keys into the final answer |

## 4. Data models

```python
class Character(BaseModel):  name, role, description, secret, motive, alibi, is_culprit: bool
class Location(BaseModel):   name, description
class Fact(BaseModel):       id, text, truth: bool          # truth=False -> a lie told by someone
class CaseBible(BaseModel):
    title, logline, setting, era, audience, tone
    characters: list[Character]; locations: list[Location]
    timeline: list[TimelineEvent]                           # what REALLY happened
    solution: Solution                                      # culprit, method, motive, final_answer
    red_herrings: list[str]
class Knot(BaseModel):       id, question, answer, requires: list[str]   # evidence ids
class Evidence(BaseModel):   id, text, token, from_puzzle: str
class ClueGraph(BaseModel):  knots, evidence, edges           # must be a DAG ending at final knot
class ChapterPlan(BaseModel): n, title, story_beats, puzzles: list[PuzzleSpec], evidence_ids, knot_ids, pages
class MysteryBook(BaseModel): bible, graph, chapters, meta_puzzle, page_plan
```

## 5. Generation pipeline — stages S1–S10 (order learned from Artefactum, see docs/REFERENCES.md)

Each stage: **AI proposes JSON → code validates (pydantic + rules) → saved as editable YAML** in
`output/<book_id>/stages/Sx_<name>.yaml`. The owner may edit any YAML; re-run from any stage with
`forge mystery build <case.yaml> --from-stage S4` (later stages are regenerated, earlier ones are read
back from YAML and re-validated). A stage that fails validation is retried with the error message
(max 2), then the build stops with the validation report. Tests use recorded fixtures (no real AI).

| Stage | Output | Validation (code) |
|---|---|---|
| S1 Brief | genre, audience, tone, length, single/series, template, **relationship ontology** of the setting (§13.1) | enums, length bounds, kid rules (no murder for kids), ontology: every type has an inverse, conflict pairs declared |
| S2 Characters | 5–8 characters: name, archetype, role, look, traits, flaw, **3 tiered secrets (high/medium/low)**, motive, alibi, **hidden agenda**; exactly 1 culprit | unique names, no near-duplicates (edit distance ≤ 2 or same first letter+length), every character has a motive, exactly one `is_culprit`, every false alibi is backed by a high-tier secret |
| S3 Relationships | directed graph over every ordered pair, typed by the S1 ontology: relation, attitude, known_secrets | **graph validation (§13.1)**: inverse edge present for every edge (A BOSS_OF B ⇒ B WORKS_FOR A), no declared conflict pair on the same pair, no isolated character, every suspect linked to victim or culprit, consistent with secrets |
| S4 Truth Timeline | what REALLY happened: events `{t_start, t_end, who[], where, what}` | nobody in two places at once, culprit has opportunity (at scene in the crime window), every false alibi contradicts ≥ 1 event (QA L4.timeline) |
| S5 Story Arc | **4 acts** (Setup → Incident → Investigation → Revelation) mapped to 10 chapters (8 for kids); each chapter has a reader **objective** + knot; ≥ 12 timeline checkpoints referenced | chapter count, act order, every knot in a chapter, twist after midpoint, every checkpoint used |
| S6 Clue Graph | causal graph (§9) | DAG, reachability, ≥ 2 evidence per knot, final depends on all chapter keys |
| S7 Evidence ↔ puzzles + artifacts | each clue: real or red herring, tier (= puzzle level), story location, discovery method (puzzle type / document), linked **case artifact** (§13.3), token + `PuzzleSpec` with constraint | ≈ balanced real/red-herring mix, every red herring points away from the culprit and is refuted by later real evidence, every artifact used by ≥ 1 clue, every token producible, generator + verify succeed |
| S8 Prose + case documents | chapter intros, letters, clippings, interrogation transcripts, **suspect dossiers**, artifact pages | grounded: only facts from the graph unlocked up to that chapter (spoiler guard L4.spoilers); reveal rules and hidden agendas respected |
| S9 Hook / teaser / book_card | marketing text (QA_SPEC §5) | L5 (no spoilers, limits, names) |
| S10 Render | Typst interior + solutions | QA L1–L4 |

## 6. Page plan (adult, ~100 pages)

| Part | Pages |
|---|---|
| Front matter (title, copyright, how to play, case file intro) | 4–6 |
| Case dossier (suspects, map, timeline sheet) | 6 |
| 10 chapters × 9 (2 story/doc + 5–6 puzzles + 1 evidence board) | 90 |
| Finale: meta-puzzle + accusation page | 4 |
| Dead-end pages | 4–6 |
| Solutions + reasoning (back) | 12–20 |

Kids (7–11): 8 chapters × 8 pages, bigger puzzles, illustrated, friendly culprit (a prank, a lost pet, a mix-up).

## 7. Starter templates (`configs/mystery/`)

1. `lighthouse.yaml` — *The Last Log of the Lighthouse Keeper* (adult, single): the keeper vanishes; his
   encrypted log hides the truth. Main puzzles: cryptogram, logic grid, sudoku codes.
2. `museum_kids.yaml` — *Junior Detectives: The Museum That Talks* (kids series): each volume one missing
   artifact; mazes, easy word search, 4x4 picture sudoku, spot-the-difference (later).
3. `legend_files.yaml` — *The Legend Files* (series, public-domain legends: Atlantis, Bermuda Triangle,
   El Dorado, Loch Ness…): each volume ends with a map fragment linking to the next.

## 8. Series bible

`series.yaml`: recurring detective(s), world rules, tone, running mystery arc, volume list, used names/puzzle
hashes (avoid repeats), cliffhanger ledger. `forge series next` creates the next volume's brief from it.

## 9. Clue graph = causal graph (idea from AymanJabr graph.json, re-implemented)

Nodes (`forge/mystery/causal_graph.py`):

| kind | meaning |
|---|---|
| `fact` | a true (or lied) statement from the truth timeline |
| `evidence` | a fact the reader *earns* (from a puzzle token or a document) |
| `knot` | a question the reader must answer to advance |
| `puzzle` | a puzzle whose verified answer yields a token |
| `chapter` | a chapter; unlocked when its entry knot is answered |
| `final` | the accusation / meta-puzzle |

Every node has `requires: [node_id]` (all must be unlocked first) and `unlocks: [node_id]`
(derived edges). Code (never the AI) owns the state:

- `available(state)` → nodes whose requirements are met and that are not yet done (state filtering,
  no spoilers of later content);
- `closure(start)` → everything unlockable from a start set (fixpoint);
- `validate()` → DAG (no cycles), every node reachable from the start, `final` reachable, each knot
  has ≥ 2 evidence requirements, at least one knot needs evidence from two different chapters, no
  single evidence node points straight at the culprit.

**Reveal rules** for characters (interrogation pages): `{character, info: fact_id, when: [evidence_id]}`
— a character only states `info` on a page placed after the reader holds every `when` evidence.
S8 must respect them and QA L4.reader_sim checks them.

## 10. Logic grid + dual solvers + case uniqueness (ideas from env-zebra, own code)

`forge/puzzles/logicgrid`:
- Seeded generator: random solution (N entities × K categories), candidate clue pool
  (`same`, `not_same`, `neighbor`, `left_of`, `immediately_left`, `position`, plus `either_or` for hard
  levels), add clues until solver 1 finds exactly one solution, then prune while still unique.
- Levels: easy 3x3 → medium 4x4 → hard 5x5 → very_hard 6x6 → extreme 7x5+ (book levels map
  `expert` → very_hard/extreme).
- Constraint `grid_solution(facts)`: the solution is built **from** the case truth (who / where /
  weapon / time) instead of random, so the solved grid states the facts of the case.
- Clue text from English templates; AI may only *rephrase* for flow. Code re-parses the rephrased
  sentence back to the same clue tuple (template matching on entity names + relation keywords); if
  it does not round-trip, the template text is kept.
- **Solver 1**: domain propagation + backtracking (own code). **Solver 2**: different algorithm —
  brute force over permutations for ≤ 5x5, OR-Tools CP-SAT (Apache-2.0) above. Both must return the
  same single solution (QA L1.dual_solver / L1.unique).
- The same engine checks **case uniqueness** (QA L4.case_unique): suspects × {place, weapon, time,
  motive} are the grid, the evidence the reader holds before the accusation page are the clues;
  both solvers must yield exactly one culprit; adding red herrings must not create a second one.

## 11. Reader simulation (`forge/qa/reader_sim.py`)

Walks the **printed page order**. The simulated reader holds only evidence from pages already
read; when it meets a puzzle it "solves" it using the verified solver output (never the stored
answer directly), turns the token into a page number with the encoder and jumps there. Checks
(QA L4.reader_sim): evidence before the knot that needs it; token → encoder → page lands on the
right page; every dead-end page points back correctly; no orphan page (every page reachable);
reveal rules respected; the meta-puzzle's verified answer equals `final_answer`. Output goes into
`qa_report.json`.

## 12. Export schema & play-test build (schema shape from csurfer/escaperoom, MIT)

`output/<book_id>/mystery_book.json`:

```json
{
  "story": {"title": "...", "text": "...", "images": []},
  "chapters": [{"n": 1, "title": "...", "pages": [12, 20], "text": "...", "unlocks": ["ch2"]}],
  "puzzles": [{"id": "pz-...", "chapter": 1, "title": "...", "text": "...", "images": [],
               "hints": ["..."], "answer": "HARBOR", "unlocks": ["ev-tide", "ch2"]}],
  "final": {"question": "Who took the lens?", "answer": "...", "explanation": "..."}
}
```

`forge mystery export-play <book_id>`:
- `--format html` (default): one self-contained static HTML page (our own code, no server): chapter
  text and puzzle images; typing the right answer unlocks the next chapter (answers stored as
  sha256 hashes so the page source does not spoil them).
- `--format escaperoom`: `{story, puzzles[{title, text, images, hints, answer}]}` compatible with
  csurfer/escaperoom's `config.schema`.

The AI play-test (QA L4.playtest) runs on this export: two agents of different models (Claude +
GPT), without answers; they must solve the case and must not name the culprit before the last
chapter. Stuck points are recorded in the QA report.

## 13. Additions from the original Artefactum post (read 2026-11-07)

Artefactum (Maria Lu, Jan 2026) generates 12-player party murder-mystery games: characters →
relationships (graph-validated) → story → clues (linked to story) → objectives (linked to props) →
Typst PDFs → web dashboard. No code or prompts are published; we adopt **ideas only**.

### 13.1 Relationship ontology + graph validation (S1, S3)
- Each setting declares its own relationship types instead of generic friend/enemy
  (`configs/mystery/ontologies/*.yaml`), each with an **inverse** (`BOSS_OF ↔ WORKS_FOR`,
  `INFORMANT_FOR ↔ HANDLER_OF`, `BLACKMAILS ↔ BLACKMAILED_BY`, `SIBLING ↔ SIBLING`) and declared
  **conflict pairs** (e.g. `TRUSTS` and `BLACKMAILED_BY` on the same ordered pair). Kids ontologies
  are friendly only (classmate, neighbour, rival, helper).
- `forge/mystery/relations.py` builds a directed graph and validates: inverse present for every edge;
  no conflict pair; no isolated character; every suspect within 2 hops of the victim/culprit; relations
  consistent with secrets. Output feeds QA L4.relations.

### 13.2 Characters with tiered secrets and hidden agendas (S2)
- 3 secrets per character (high / medium / low). The high-tier secret explains the false alibi
  (an innocent suspect lies to hide it), which is how red herrings become fair: the lie is exposed by
  evidence the reader can earn.
- Hidden agenda = what the character wants to protect; it drives **reveal rules** (§9) on
  interrogation pages ("Mara only admits the late visit after you show the torn ticket").

### 13.3 Clues ↔ story ↔ artifacts (S7) — book version of "props"
- Party games need physical props; a book needs **case artifacts** printed as pages or inserts:
  letters, ledgers, tickets, photographs (illustrated later in P6), maps, tide tables.
  `Artifact {id, kind, title, description, first_page, clue_ids}`.
- Clue record: `{id, real|red_herring, tier, story_location, discovery: puzzle|artifact|interview,
  artifact_id?, evidence_id, points_to}`. Target mix ≈ 50 % real / 50 % red herring (configurable);
  tiers follow the chapter difficulty curve.
- Party "objectives" become **reader objectives** per chapter ("Find out who left the lighthouse at
  2 AM") printed on the chapter opener, each tied to the chapter's knot.

### 13.4 Story structure (S5)
- 4 acts mapped to chapters (adult 10: Setup 1–2, Incident 3, Investigation 4–8, Revelation 9–10).
- Timeline with ≥ 12 checkpoints; culprit motive written as a layered 3-part twist (surface motive,
  hidden motive, trigger), all grounded in S4 facts.

### 13.5 Review dashboard (owner aid)
- Artefactum ships a GM dashboard with a relationship graph. We generate `review/<book_id>/case.html`
  (self-contained, our own code, no CDN): relationship graph, timeline, clue → artifact → page map.
  It is a review aid only, never part of the printed book.

### 13.6 Not adopted
- DSPy / Groq / Llama: our AI layer already uses typed pydantic schemas + validation + retry + cache
  (same idea as typed signatures) behind `forge/ai`; provider choice stays Anthropic/OpenAI.
- Party-game artifacts (GM script, voting system) — not applicable to single-reader books.

## 14. Blueprints, page planner, framed AI art, colour-by-number reveals (owner rules 2026-11-07)

**Blueprint library** `blueprints/<line>/line.yaml` (escape_adult, escape_kids, mystery_adult,
adventure_kids). Page types: inner_cover, how_to_play, story, dossier, reference, main_puzzle,
supporting_clues, interlude, code_register, evidence_worksheet, final_meta, cbn_reveal, hints, solutions,
certificate, cutout, notes. Each page type = a Typst template + **zones** in mm relative to the trim box
(z-ordered): `art` (AI image), `puzzle` (vector game), `text`, `input` (code boxes / handwriting),
`header`, `footer`, `watermark`; the knock-out zone is derived from puzzle + text + input. Layout variants
per page type (e.g. main_puzzle: art_top / art_side / frame). `forge blueprint preview <line>` renders
every page type with coloured zones for owner review.

**Page planner** (input: case bible + story arc + clue graph + blueprint + targets: ≥ 50 game pages,
difficulty curve, audience, edition) computes: number of puzzles, mechanism per puzzle (varied, never the
same twice in a row, rising curve), supporting pages, interludes, 4 hint tiers per puzzle, cbn_reveal
positions, code check table (bound/spiral) or host pack (digital kit). Output `page_plan.yaml` (page no.,
page type, variant, puzzle ids, text blocks, art requests, codes in/out), editable, rebuild with
`--from-stage page_plan`. Validation: page count, every clue-graph node placed, no unintended blank page,
even total, cut-outs single-sided.

**Framed AI art** — never redraws a game. Per art zone an `art_request`: exact pixel size at 300 DPI,
aspect, **mask PNG** (white = paint, black = leave plain paper), style bible, character references,
scene from the script, optional render of the puzzle as a *theme reference*. Mandatory prompt clauses:
no text, no letters, no numbers, keep masked areas empty. Exported to `art_requests/` for the HALOSPARK
image tool; `forge art import` brings images back. Compositor order: paper → AI art → watermark
(knocked out) → vector game + text + input boxes (always on top, rendered by code).

**Colour-by-number reveal** (`forge/puzzles/cbn`): type A "colour reveal" (numbers → colours → a digit /
letter / symbol appears = next code); type B "colour by answer" (each region holds a mini puzzle whose
answer picks the colour). Level 1 (first): geometric mosaics generated entirely by code with the code
glyph embedded in the dark colour; level 2 (later): line art from the HALOSPARK image tool, vectorised,
closed regions split along the glyph outline. Palette 4–8 colours by audience with numbered swatches;
grayscale editions use patterns/symbols if needed. Solver/QA: render the coloured result from the answers
→ glyph matching must read the right code with enough contrast and size; every region closed, numbered
and large enough to write in; type B mini puzzles have unique answers. Solutions show the coloured image.

## 15. General rule for every escape / mystery / adventure line (incl. CBN Mystery) — owner rules 2026-11-07

**All clues required.** The final answer (culprit name and/or unlock code / key location) can be
deduced **only when every clue is combined**. This is a hard rule for every blueprint
(`escape_adult`, `escape_kids`, `mystery_adult`, `adventure_kids`, `cbn_mystery`).

Mandatory QA (`L4.all_clues_required`, BLOCKER), run by `forge/mystery/necessity.py`:
- the case declares a **candidate space** (suspects × attributes, or every code of the given length /
  alphabet, or every location) and the clues as **declarative predicates** (no free text in the check);
- with **all** clues → exactly **1** candidate remains, and it equals the declared answer;
- for **each** clue, dropping it alone → the solver finds **> 1** candidate (no redundant clue);
- the report lists the survivors for every dropped clue (evidence for the owner).

Clue predicate language (JSON/YAML, stored in the case bible and the manifest):
`{field, op, value}` with `op` ∈ `eq ne in not_in lt le gt ge`, plus `{"any_of": [...]}`,
`{"not": {...}}`, `{"distinct": [fields]}` and derived fields for codes (`d1..dn`, `sum`, `even_count`).

The book still prints the full solutions at the back; the website is an extra for rewards. The **last
page** of these lines is the `case_vault` page: "Submit your final answer at <DOMAIN> to unlock rewards"
+ a QR code that opens the book's own page (`https://<DOMAIN>/solve/<book_id>`), see docs/CASEVAULT.md.

## 16. CBN Mystery line (ROADMAP P8)

A colour-by-number mystery: each chapter's colouring page (type A or B, §14) reveals one **clue glyph**
(letter, digit or symbol); short story pages and evidence cards give the meaning of each glyph. The
clue glyphs combined with the evidence narrow the suspects (or the code digits) to exactly one — the
§15 rule applies unchanged (drop any reveal → > 1 candidate). Audience: kids 6–8 (4-colour palettes,
3–4 reveals) and adults (6–8 colours, 6–8 reveals). Blueprint `blueprints/cbn_mystery/line.yaml`.
