# New game types for the mystery series (research 2026-11-21)

Built now: word search, crossword, sudoku, maze, cryptogram, scramble, shift cipher, number lock, colour by number.
Golden rules still apply: own generator (deterministic seed) + independent solver; no GPL code.

## Reference code (licences checked)
- Simon Tatham's Portable Puzzle Collection — MIT. C sources with generators + uniqueness checks for
  Pattern (nonogram), Keen (calcudoku), Unequal (futoshiki), Towers (skyscrapers), Light Up, Bridges, Tents, Slant, Loopy.
  Use as algorithm reference; we write Python.
- puzzlekit (PyPI) — MIT, solvers only (OR-Tools CP-SAT, Apache-2.0) for 100+ genres: usable as the *independent solver*
  in tests/verification. It does not generate.

## Proposed types (fit with the stories)
| Type | What the reader does | Why it fits | Effort |
|---|---|---|---|
| Wordoku | sudoku with 9 letters; the shaded cells spell a word | owner's request; keyword out of a logic grid | S (reuse sudoku + rustoku) |
| Nonogram | shade cells from row/column numbers; a picture appears | second "hidden picture" that is pure logic | M |
| Calcudoku | fill a grid, cages with sums/products | number-lock style chapters | M |
| Kakuro | crossword of number sums | vault / ledger chapters | M |
| Futoshiki | grid with < > signs between cells | quick logic, ages 9+ | S |
| Skyscrapers (Towers) | building heights seen from the edges | towns, pagodas, tombs | S |
| Light Up | place lanterns so every square is lit | lanterns in Vanished Star / tombs | M |
| Bridges | connect islands with bridges | harbour / river chapters | M |
| Star Battle | place stars, one per row/column/region | "the vanished star" | M |
| Word ladder | change one letter per step (BELL → ROPE) | keyword in every rung | S |
| Pigpen / Morse / Semaphore | symbol ciphers | escape-room feel, art-light | S each |
| Book cipher | page-line-word numbers into the story text | uses the book's own story | S |
| Acrostic | first letters of answers spell the clue | wraps any word set | S |
| Bearings | follow compass directions on a map | tomb / map volumes | M (needs map art) |
| Spot the difference | two Gemini pictures with code-made changes | kids and gift buyers love it | M (art + code diff) |
| Rebus | picture riddles | needs drawn icons | L |

Suggested first batch: Wordoku, Nonogram, Light Up, Star Battle, Word ladder, Pigpen.
