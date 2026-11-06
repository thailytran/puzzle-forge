from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from forge.layout.trim import (
    TRIMS,
    gutter_for,
    load_kdp_rules,
    margins_for,
    pad_page_count,
)


def test_trims_present() -> None:
    assert set(TRIMS) == {"8.5x11", "8x10", "6x9", "8.5x8.5"}
    assert TRIMS["6x9"].width_in == 6.0
    assert TRIMS["6x9"].height_in == 9.0


@pytest.mark.parametrize(
    ("pages", "gutter"),
    [(24, 0.375), (150, 0.375), (151, 0.5), (300, 0.5), (301, 0.625), (700, 0.75), (828, 0.875)],
)
def test_gutter_table(pages: int, gutter: float) -> None:
    assert gutter_for(pages) == gutter


def test_gutter_out_of_range() -> None:
    with pytest.raises(ValueError):
        gutter_for(900)


def test_margins_respect_minimums() -> None:
    rules = load_kdp_rules()
    m = margins_for(120)
    assert m.inside >= gutter_for(120)
    for v in (m.outside, m.top, m.bottom):
        assert v >= rules.outside_min_in


@given(st.integers(min_value=1, max_value=820))
def test_pad_even_and_min(n: int) -> None:
    p = pad_page_count(n)
    assert p % 2 == 0
    assert p >= max(n, 24)
    assert p - max(n, 24) <= 1


def test_pad_without_minimum() -> None:
    assert pad_page_count(5, min_pages=0) == 6
    assert pad_page_count(6, min_pages=0) == 6
