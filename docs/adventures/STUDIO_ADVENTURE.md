# HALOSPARK Studio ↔ Puzzle Forge — Adventure line (P9.4 contract)

Forge decides and verifies everything the reader needs (answers, keys, slots, object lists, page
order). Studio runs ChatGPT / Gemini and the owner review, then hands pictures and ticks back.

## 1. Job folder (Forge → Studio)

`uv run forge adventure studio configs/adventures/<book>.json` writes
`output/adventure/<book_id>/studio/`:

| File | For | Content |
|---|---|---|
| `writing_brief.json` | ChatGPT | rules, FORBIDDEN words (every puzzle answer + the final word), the frame, and `return_json` = the exact JSON to send back |
| `art_requests.json` | Gemini | one entry per picture: `id`, `zone`, `aspect`, `brief`, `style`, `refs` / `characters` (cast lock), `objects` for search scenes and icon sheets |
| `selfcheck_prompt.txt` | Gemini vision | after a search scene is drawn: "where is each object" → JSON list |
| `review.json` | owner UI | `{"ch1": {"teacup": false, ...}}` — never overwritten once it exists |

ChatGPT's reply is merged with `uv run forge adventure merge <frame.json> <reply.json>`: only text
fields are copied (story, teaser, captions, puzzle intro / explain, listing) and the whole frame
check runs again — a reply that leaks an answer or breaks a rule is refused.

## 2. Art keys (Studio → Forge, folder passed as `--art`)

File name = key with `_` instead of `:` (Windows): `search_ch1.png` is `search:ch1`.

| Key | Aspect | Printed as |
|---|---|---|
| `char:<id>` | 3:2 | reference sheet only (cast lock), never printed |
| `cover` | 3:4 | cover.pdf (vivid painted, badges PUZZLES / SEARCH / COLORING, story-edition seal) |
| `prologue`, `epilogue`, `vignette:chN` | 5:4 | line-art vignette in the lower part of the story page |
| `search:chN` | 3:4 | full-page line-art search scene, all objects once, right fifth kept calm |
| `icons:chN` | 4:3 | icon sheet: 4 columns, objects in list order (cut by `split_icon_sheet`) |
| `map` | 3:4 | the library map, a colouring page that keeps the chapter spreads on the left |
| `design:border` | page | optional ornate frame with a transparent centre (else Forge draws a frost frame) |

Pictures are converted to clean black-and-white line art for colouring. A missing picture prints a
labelled placeholder; `manifest.json → art.missing` lists them.

## 3. Hidden-object check (code cannot verify art)

1. Gemini draws `search:chN` with the object list from `art_requests.json`.
2. Gemini self-check (`selfcheck_prompt.txt`) → Studio stores the reply in
   `selfcheck.json` as `{"chN": [{"name", "x", "y", "r"}]}` (fractions of the picture).
3. Owner opens the review UI: scene with the marks, one checkbox per object → `review.json`.
4. Forge prints a numbered ring on the answer page only for objects that are **marked and ticked**.
   `manifest.json → search_check.chN` = `{objects, marked, ticked, unmarked, not_ticked, ok}`;
   `ready_for_review` is true only when every chapter is ok and no art is missing.

An object that Gemini did not draw: re-draw the scene (never edit the list by hand; a new list
must pass `forge adventure check`).

## 4. Studio tab (to build in halospark-suite)

Same layout as the Coloring Pages tabs: **Story** (ChatGPT brief → reply → `forge adventure merge`),
**Art** (queue `art_requests.json`, cast sheets first), **Search check** (self-check + tick UI writing
`review.json`), **Build** (`forge adventure build --art <folder>`), then covers, listing images
(cover mock-up · open spread · HOW TO PLAY board over DISCOVER / EXPLORE / COLOR tiles · band of the
three activities), SEO and deliverables as for the other lines.
