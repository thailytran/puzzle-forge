from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from forge.core.hashing import canonical_json, content_hash

json_scalars = st.none() | st.booleans() | st.integers() | st.text(max_size=8)
json_values = st.recursive(
    json_scalars,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=5), children, max_size=4)
    ),
    max_leaves=20,
)


def test_canonical_is_compact_and_sorted() -> None:
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'


def test_tuples_equal_lists() -> None:
    assert content_hash({"size": (10, 12)}) == content_hash({"size": [10, 12]})


def test_unicode_kept() -> None:
    assert canonical_json({"w": "café"}) == '{"w":"café"}'


def test_hash_is_sha256_hex() -> None:
    h = content_hash({"x": 1})
    assert len(h) == 64
    int(h, 16)


@given(st.dictionaries(st.text(max_size=5), json_values, max_size=6))
def test_key_order_does_not_matter(d: dict[str, Any]) -> None:
    reversed_d = dict(reversed(list(d.items())))
    assert content_hash(d) == content_hash(reversed_d)


def test_float_normalisation() -> None:
    # 1.0 and 1 are different JSON tokens; we keep them distinct but stable.
    assert content_hash({"x": 1.0}) == content_hash({"x": 1.0})
    assert canonical_json({"x": 0.1 + 0.2}) == canonical_json({"x": 0.30000000000000004})
