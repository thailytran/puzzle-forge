from __future__ import annotations

import pytest

from forge.wordlists import available_themes, is_blocked, normalize_word, theme_words


def test_normalize() -> None:
    assert normalize_word("sea horse") == "SEAHORSE"
    assert normalize_word("T-Rex") == "TREX"


def test_themes_have_enough_words() -> None:
    themes = available_themes()
    assert len(themes) >= 20
    for t in themes:
        words = theme_words(t)
        assert len(words) >= 25, t
        assert all(w.isalpha() and w.isupper() for w in words)
        assert len(set(words)) == len(words)


def test_no_blocked_words_in_lists() -> None:
    for t in available_themes():
        assert not any(is_blocked(w) for w in theme_words(t))


def test_blocklist() -> None:
    assert is_blocked("kill")
    assert not is_blocked("shell")


def test_unknown_theme() -> None:
    with pytest.raises(KeyError):
        theme_words("does not exist")
