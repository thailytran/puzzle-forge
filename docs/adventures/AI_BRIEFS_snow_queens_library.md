# Briefs for ChatGPT and Gemini — The Snow Queen's Library

Source of truth: `configs/adventures/snow_queens_library.json` (case frame, 8 chapters, final word EVERGLOW).
Rules for both: English book text; no copied IP; gentle adult tone; **never invent or change a puzzle answer** — answers are fixed in the frame and the code builds + verifies every puzzle.

## ChatGPT (writing) — tasks, in order
1. **Polish the 8 chapter stories** (keep the plot, the key clue and the names; 100–130 words each; second person; keep the sentence that places the key/clue; no new objects that are not in the hidden-object list or the cast).
2. **Search-page captions**: for each chapter write 12 one-line object descriptions (≤8 words, the object name first) matching `hidden_objects`.
3. **Puzzle flavour text** (code builds the puzzles): one intro line for Puzzle A and one for Puzzle B per chapter (do not reveal answers or the method beyond "decode / navigate / find the pattern").
4. **Answer-page explanations**: 2 sentences per puzzle explaining how the answer is reached (given the answer in the frame).
5. **Cover + listing copy**: back-cover blurb (≤90 words), promise line, 5 bullets, Etsy title (≤140 chars), Shopify description. Must include the line "inspired by Hans Christian Andersen's The Snow Queen (1844)".
6. **Self-check**: list any sentence that leaks a puzzle answer or contradicts the cast look.
Return JSON matching the frame fields (`chapters[].story`, `chapters[].captions`, `chapters[].puzzle_a.intro`, `chapters[].puzzle_b.intro`, `chapters[].explain`, `listing`).

## Gemini (drawing) — page list (line-art unless stated)
- **Cast sheets** (3:2, colour OK, for consistency): Ottoline Finch, Plume, the Snow Queen (Isolde Vane), the Restorer (hands/coat only).
- **Location sheet** (3:2): the Library of Aldermere exterior + the 8 rooms as thumbnails.
- **Cover** (3:4, vivid luminous painted scene): the library on its snowy hill at dusk, warm lit windows, Plume on the gatepost, the Snow Queen's silhouette in the top window; ornate title area; three round badges PUZZLES / SEARCH / COLORING; round "story edition" seal. No other text.
- **8 story vignettes** (line-art, 5:4): one per chapter, from the chapter story, nothing that is not in the text.
- **8 search scenes** (line-art, 3:4 full page, ornate border): the room full of detail containing all 12 `hidden_objects` (each clearly drawn once, large enough to find, no text); Gemini self-check returns a list of the objects it drew with approximate position (for the answer page) — the owner ticks each object in the review UI.
- **Chapter heading banners / border** (shared): ornate frost-lace border + "Chapter N | Title" ribbon (text by code, not by Gemini).
- **Listing images** (4:3 ×10): cover mock-up; open spread; HOW TO PLAY board over DISCOVER / EXPLORE / COLOR tiles; bottom band naming the three activities.
Style: clean even outlines, no grey fill, no hatching blobs; kids' safety not needed (adult), but gentle. Same characters on every page (cast lock).
