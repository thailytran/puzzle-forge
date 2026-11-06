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

## 5. Generation pipeline (each stage validated, cached, editable by the owner)

1. **Brief** (owner): template or free text, audience, length, tone, single/series.
2. **Case Bible** (AI → JSON) → validator: one culprit, consistent timeline, every character has motive/alibi.
3. **Clue Graph** (AI proposes, code validates): DAG, every knot reachable, ≥2 evidence per knot, final knot
   depends on all chapter keys, no evidence reveals the culprit alone.
4. **Chapter plan** (code): 10 chapters × ~9 pages; assigns puzzle types by audience + difficulty curve.
5. **Puzzle generation** (code): each puzzle built with constraints so it yields its token → verified.
6. **Prose** (AI): chapter intros, case-file documents (letters, newspaper clippings, interrogation notes),
   transitions; references only facts allowed up to that chapter (spoiler guard checked by code + AI).
7. **Meta-puzzle** + final reveal + solutions with step-by-step reasoning.
8. **Playtest** (AI agent sees only reader-visible text + its own puzzle answers from the solver) → reports
   where it got stuck / could guess early. Fix loop.
9. **Layout** → interior.pdf; **cover + listing**.

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
