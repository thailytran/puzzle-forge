"""Fixed English front/back matter text (book content is English; AI copy arrives in P2.4)."""

from __future__ import annotations

HOW_TO_PLAY: dict[str, str] = {
    "wordsearch": "Find every word from the list in the grid. Words run in straight lines "
    "and may go across, down or diagonally (in harder puzzles also backwards). Circle each word.",
    "sudoku": "Fill every empty square so that each row, each column and each outlined box "
    "contains every number exactly once. Each puzzle has exactly one solution.",
    "maze": "Start at START and find the only path to FINISH without crossing any wall.",
    "scramble": "Unscramble the letters to make a word that fits the theme. "
    "Every scramble has exactly one answer.",
    "cryptogram": "Each letter of the message has been swapped for a different letter. "
    "Work out the code to reveal the quote. Some letters are given to get you started.",
    "crossword": "Fit every word from the list into the grid so that all crossing letters match.",
    "cbn": "Colour each square with the colour of its number (or of the answer to its sum). "
    "When every square is coloured, a secret code appears.",
}

COPYRIGHT = (
    "Copyright © {year} {author}. All rights reserved. No part of this book may be reproduced "
    "without written permission from the publisher, except for brief quotations in reviews. "
    "Puzzles are original and were checked by computer for a correct solution."
)
ABOUT = (
    "Every puzzle in this book was created for this edition and verified by an independent "
    "solver, so each one has a correct answer in the solutions section."
)
THANK_YOU = (
    "Thank you for solving with us! If you enjoyed this book, a short review helps other puzzle "
    "fans find it."
)
