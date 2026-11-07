"""Core data models shared by all puzzle types (see docs/SPEC.md §1, §5)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from forge.core.hashing import content_hash as _content_hash

Level = Literal["very_easy", "easy", "medium", "hard", "expert"]
LEVELS: tuple[Level, ...] = ("very_easy", "easy", "medium", "hard", "expert")
Audience = Literal["kids_6_8", "kids_9_12", "teen", "adult", "senior_large_print"]
# Reader-facing names shown in books and listings
LEVEL_LABELS: dict[str, str] = {
    "very_easy": "Beginner",
    "easy": "Easy",
    "medium": "Intermediate",
    "hard": "Hard",
    "expert": "Expert",
}
AUDIENCES: tuple[Audience, ...] = ("kids_6_8", "kids_9_12", "teen", "adult", "senior_large_print")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Mystery constraints (SPEC §5) -------------------------------------------------------


class HiddenMessage(_Model):
    """Word search: unused letters, read row by row, spell `text`."""

    kind: Literal["hidden_message"] = "hidden_message"
    text: str


class ShadedCells(_Model):
    """Sudoku / crossword / kakuro: values in `cells` (row, col) read `expect`."""

    kind: Literal["shaded_cells"] = "shaded_cells"
    cells: list[tuple[int, int]]
    expect: str


class PathLetters(_Model):
    """Maze: letters on the solution path spell `seq`; decoys off-path."""

    kind: Literal["path_letters"] = "path_letters"
    seq: str


class AnswerIs(_Model):
    """Scramble / cryptogram / riddle: final answer equals `word`."""

    kind: Literal["answer_is"] = "answer_is"
    word: str


class GridSolution(_Model):
    """Logic grid: solution must contain the given facts (e.g. {"who": "Ada", "where": "pier"})."""

    kind: Literal["grid_solution"] = "grid_solution"
    facts: list[dict[str, str]]


class PageNumber(_Model):
    """Any type: token is converted to page number `n` the reader turns to."""

    kind: Literal["page_number"] = "page_number"
    n: int = Field(ge=1)


Constraint = Annotated[
    HiddenMessage | ShadedCells | PathLetters | AnswerIs | GridSolution | PageNumber,
    Field(discriminator="kind"),
]


# --- Puzzle models -----------------------------------------------------------------------


class PuzzleSpec(_Model):
    type: str
    level: Level
    audience: Audience
    theme: str | None = None
    words: list[str] | None = None
    size: tuple[int, int] | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    constraints: list[Constraint] = Field(default_factory=list)


class DifficultyScore(_Model):
    score: float = Field(ge=0, le=100)
    label: Level
    features: dict[str, float] = Field(default_factory=dict)


class VerifyReport(_Model):
    ok: bool
    unique: bool | None = None
    solver: str
    messages: list[str] = Field(default_factory=list)


class SolveResult(_Model):
    solved: bool
    solution: dict[str, Any] | None = None
    solutions_found: int = 0  # capped count (2 means "more than one")
    stats: dict[str, float] = Field(default_factory=dict)


class Puzzle(_Model):
    id: str
    type: str
    spec: PuzzleSpec
    seed: int
    data: dict[str, Any]
    solution: dict[str, Any]
    token: str | None = None
    content_hash: str
    difficulty: DifficultyScore | None = None
    verify: VerifyReport | None = None


def make_puzzle_id(type_: str, content_hash: str) -> str:
    """Deterministic id: `<type>-<first 16 hex of content_hash>`.

    SPEC suggested a ULID; we use a hash-derived id instead so that the same spec + seed
    yields a byte-identical Puzzle (golden rule 3).
    """
    return f"{type_}-{content_hash[:16]}"


def build_puzzle(
    spec: PuzzleSpec,
    seed: int,
    data: dict[str, Any],
    solution: dict[str, Any],
    token: str | None = None,
) -> Puzzle:
    """Create a Puzzle with its content hash and id filled in."""
    h = _content_hash({"type": spec.type, "data": data})
    return Puzzle(
        id=make_puzzle_id(spec.type, h),
        type=spec.type,
        spec=spec,
        seed=seed,
        data=data,
        solution=solution,
        token=token,
        content_hash=h,
    )


_LEVEL_BANDS: tuple[tuple[float, Level], ...] = (
    (20.0, "very_easy"),
    (40.0, "easy"),
    (60.0, "medium"),
    (80.0, "hard"),
)


def level_from_score(score: float) -> Level:
    """Map a 0..100 score to a level label (bands of 20)."""
    for upper, label in _LEVEL_BANDS:
        if score < upper:
            return label
    return "expert"
