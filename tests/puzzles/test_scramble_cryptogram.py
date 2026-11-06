from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from forge.core.models import LEVELS, PuzzleSpec
from forge.core.protocol import PuzzleType, RenderCtx
from forge.puzzles.base import GenerationError
from forge.puzzles.cryptogram import Cryptogram, count_decodings, derangement, encipher
from forge.puzzles.scramble import Scramble, candidates
from forge.wordlists import available_themes
from forge.wordlists.dictionary import anagrams, is_common, quotes

SC, CG = Scramble(), Cryptogram()
CTX = RenderCtx(width_in=7.0, height_in=9.0)
THEMES = [t for t in available_themes() if t != "short_words"]


def spec(type_: str, level: str = "easy", **kw: object) -> PuzzleSpec:
    data: dict[str, object] = {"type": type_, "level": level, "audience": "adult"}
    data.update(kw)
    return PuzzleSpec.model_validate(data)


def test_types() -> None:
    assert isinstance(SC, PuzzleType)
    assert isinstance(CG, PuzzleType)


def test_dictionary() -> None:
    assert "SILENT" in anagrams("LISTEN")
    assert is_common("HOUSE")


def test_quotes_are_common_words() -> None:
    from forge.puzzles.cryptogram import plain_words

    for text, source in quotes():
        assert source
        assert all(is_common(w) for w in plain_words(text)), text


# ------------------------------------------------------------------ scramble


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    seed=st.integers(min_value=0, max_value=2**32),
    level=st.sampled_from(LEVELS),
    theme=st.sampled_from(THEMES),
)
def test_scramble_verifies(seed: int, level: str, theme: str) -> None:
    try:
        p = SC.generate(spec("scramble", level, theme=theme), seed)
    except GenerationError:
        return  # theme too small for this length band: allowed, must fail loudly
    assert SC.verify(p).ok
    for s, a in zip(p.data["items"], p.solution["answers"], strict=True):
        assert s != a
        assert candidates(s, p.data["word_bank"]) == {a}


def test_scramble_bonus_answer() -> None:
    p = SC.generate(
        spec("scramble", constraints=[{"kind": "answer_is", "word": "harbor"}], theme="ocean"), 3
    )
    assert p.token == "HARBOR"
    assert sorted(p.data["bonus"]) == sorted("HARBOR")
    assert SC.verify(p).ok


def test_scramble_bonus_ambiguous_rejected() -> None:
    with pytest.raises(GenerationError):
        SC.generate(
            spec("scramble", constraints=[{"kind": "answer_is", "word": "listen"}], theme="ocean"),
            3,
        )


def test_scramble_deterministic() -> None:
    a = SC.generate(spec("scramble", theme="space"), 5)
    assert a.model_dump_json() == SC.generate(spec("scramble", theme="space"), 5).model_dump_json()


# ------------------------------------------------------------------ cryptogram


def test_count_decodings_full_hints_unique() -> None:
    from forge.core.seeds import make_rng

    key = derangement(make_rng(1))
    words = ["THE", "EARLY", "BIRD"]
    cw = [encipher(w, key) for w in words]
    fixed = {key[c]: c for c in "THEARLYBID"}
    assert count_decodings(cw, fixed) == (1, True)


@pytest.mark.parametrize("level", LEVELS)
def test_cryptogram_verifies(level: str) -> None:
    p = CG.generate(spec("cryptogram", level), 4)
    rep = CG.verify(p)
    assert rep.ok, rep.messages
    assert rep.unique


def test_cryptogram_answer_is() -> None:
    p = CG.generate(spec("cryptogram", constraints=[{"kind": "answer_is", "word": "lantern"}]), 1)
    assert p.token == "LANTERN"
    assert "LANTERN" in p.solution["plain"]
    assert CG.verify(p).ok


def test_cryptogram_custom_text_with_name() -> None:
    text = "MEET ELIZA AT THE OLD HARBOR"
    p = CG.generate(spec("cryptogram", options={"text": text}), 2)
    assert p.solution["plain"] == text
    hints = set(p.data["hints"].values())
    assert set("ELIZA") <= hints  # uncommon word -> its letters are given


def test_cryptogram_tamper_detected() -> None:
    p = CG.generate(spec("cryptogram"), 3)
    bad = p.model_copy(update={"data": {**p.data, "hints": {}}})
    assert not CG.verify(bad).ok


def test_cryptogram_deterministic() -> None:
    a = CG.generate(spec("cryptogram", "hard"), 8)
    assert a.model_dump_json() == CG.generate(spec("cryptogram", "hard"), 8).model_dump_json()


@pytest.mark.typst
@pytest.mark.parametrize("type_", ["scramble", "cryptogram"])
def test_render_pdf(tmp_path: Path, type_: str) -> None:
    from forge.puzzles.preview import preview_pdf
    from forge.puzzles.registry import get_puzzle_type

    p = get_puzzle_type(type_).generate(spec(type_, theme="animals"), 2)
    assert preview_pdf(p, tmp_path / "p.pdf").stat().st_size > 1000
