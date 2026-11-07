# Third-party notices

Only MIT / BSD / Apache / Expat / OFL / public-domain material ships inside Puzzle Forge
(CLAUDE.md golden rule 6). Full license texts live in `licenses/`.

| Component | Use | License | Text |
|---|---|---|---|
| rustoku (PyPI) | sudoku technique trace + cross-check | MIT | package metadata |
| typst (PyPI, compiler fallback) / Typst CLI | PDF rendering | Apache-2.0 | package metadata |
| pypdf | PDF inspection (QA) | BSD-3-Clause | package metadata |
| pypdfium2 (+ PDFium) | QA: rasterize pages, text with positions/sizes, images | Apache-2.0 / BSD-3-Clause | package metadata |
| Pillow | QA: ink bounding boxes, thumbnails | MIT-CMU (HPND) | package metadata |
| pydantic, typer, rich, PyYAML, python-dotenv | core | MIT / BSD | package metadata |
| OR-Tools (planned, PQ/P3) | CP-SAT second solver | Apache-2.0 | package metadata |
| Atkinson Hyperlegible, Courier Prime | fonts | OFL-1.1 | `licenses/OFL-*.txt` |
| ENABLE word list | dictionary | Public domain | `forge/wordlists/LICENSES.md` |
| SCOWL (sizes 10–35) | common-English list | SCOWL permissive (notice required) | `licenses/SCOWL.txt` |
| csurfer/escaperoom | **JSON schema shape only** for `forge mystery export-play` (`forge/mystery/export_play.py`) | MIT © 2021 Vishwas B Sharma | `licenses/escaperoom.txt` |

Ideas only (no code copied, independent re-implementation), see `docs/REFERENCES.md`:
GeneralReasoning/env-zebra (README says MIT but the repo has no LICENSE file → treated as ideas-only),
AymanJabr/Escape-the-room-AI-stats-game (no license), Artefactum mystery-game-generator blog.
