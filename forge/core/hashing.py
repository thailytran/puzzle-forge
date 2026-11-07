"""Canonical JSON serialisation and content hashing.

`content_hash` is the identity of a puzzle in the registry: two puzzles with the same
canonical `data` are duplicates, regardless of seed, id or spec.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _normalise(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _normalise(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_normalise(v) for v in obj]
    if isinstance(obj, set | frozenset):
        return sorted(_normalise(v) for v in obj)
    if hasattr(obj, "model_dump"):
        return _normalise(obj.model_dump(mode="json"))
    return obj


def canonical_json(obj: Any) -> str:
    """Stable JSON: sorted keys, no whitespace, tuples as lists, UTF-8 kept."""
    return json.dumps(
        _normalise(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_hash(obj: Any) -> str:
    """sha256 hex digest of `canonical_json(obj)`."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
