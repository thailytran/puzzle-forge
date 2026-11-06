"""Name → PuzzleType lookup."""

from __future__ import annotations

from forge.core.protocol import PuzzleType


def get_puzzle_type(name: str) -> PuzzleType:
    types = all_puzzle_types()
    if name not in types:
        raise KeyError(f"unknown puzzle type {name!r}; available: {', '.join(sorted(types))}")
    return types[name]


def all_puzzle_types() -> dict[str, PuzzleType]:
    from forge.puzzles.cryptogram import Cryptogram
    from forge.puzzles.maze import Maze
    from forge.puzzles.scramble import Scramble
    from forge.puzzles.sudoku import Sudoku
    from forge.puzzles.wordsearch import WordSearch

    return {t.name: t for t in (WordSearch(), Sudoku(), Maze(), Scramble(), Cryptogram())}
