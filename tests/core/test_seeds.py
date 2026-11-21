from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from forge.core.seeds import MAX_SEED, derive_seed, make_rng


def test_derive_is_deterministic() -> None:
    assert derive_seed(42, "wordsearch", 3) == derive_seed(42, "wordsearch", 3)


def test_derive_differs_by_part() -> None:
    assert derive_seed(42, "wordsearch", 3) != derive_seed(42, "wordsearch", 4)
    assert derive_seed(42, "a", "bc") != derive_seed(42, "ab", "c")


@given(st.integers(min_value=0, max_value=MAX_SEED), st.text(max_size=10))
def test_derive_in_range(master: int, part: str) -> None:
    s = derive_seed(master, part)
    assert 0 <= s <= MAX_SEED


def test_rng_reproducible() -> None:
    a = make_rng(7)
    b = make_rng(7)
    assert [a.random() for _ in range(5)] == [b.random() for _ in range(5)]
