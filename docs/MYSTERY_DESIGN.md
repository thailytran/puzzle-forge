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
| S1 Brief | genre, audience, tone, length, single/series, template | enums, length bounds, kid rules (no murder for kids) |
| S2 Characters | 5–8 characters: name, role, look, secret, motive, alibi; exactly 1 culprit | unique names, no near-duplicates (edit distance ≤ 2 or same first letter+length), every character has a motive, exactly one `is_culprit` |
| S3 Relationships | matrix for every pair: relation, attitude, known_secrets | symmetric relation types, consistent with secrets (A cannot "not know" a secret A appears in) |
| S4 Truth Timeline | what REALLY happened: events `{t_start, t_end, who[], where, what}` | nobody in two places at once, culprit has opportunity (at scene in the crime window), every false alibi contradicts ≥ 1 event (QA L4.timeline) |
| S5 Story Arc | 10 chapters (8 for kids): knots, climax, twist, ending | chapter count, every knot assigned to a chapter, twist after midpoint |
| S6 Clue Graph | causal graph (§9) | DAG, reachability, ≥ 2 evidence per knot, final depends on all chapter keys |
| S7 Evidence ↔ puzzles | each evidence: token + `PuzzleSpec` with constraint | every token producible by its puzzle type, generator + verify succeed |
| S8 Prose + case documents | chapter intros, letters, clippings, interrogation transcripts | grounded: only facts from the graph unlocked up to that chapter (spoiler guard L4.spoilers); reveal rules respected |
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
