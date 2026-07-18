"""
sparcli.input.validate
======================

Defines validation callbacks and character filters for text prompts.

A :data:`Validator` inspects a whole input value and returns an error message
(or ``None`` when the value is acceptable). A :data:`CharFilter` decides whether
a single typed character is allowed. The builtins here cover the common cases:
non-empty input, minimum length, and digit / decimal / alphabetic /
alphanumeric / no-space character sets.
"""

from __future__ import annotations

from collections.abc import Callable

# Returns an error message for a bad value, or ``None`` when it is acceptable.
Validator = Callable[[str], str | None]

# Decides whether a single typed character is accepted.
CharFilter = Callable[[str], bool]


def non_empty() -> Validator:
    """Returns a validator that rejects empty (whitespace-only) input."""

    def validate(value: str) -> str | None:
        return None if value.strip() else "must not be empty"

    return validate


def min_len(minimum: int) -> Validator:
    """Returns a validator requiring at least ``minimum`` characters."""

    def validate(value: str) -> str | None:
        if len(value) < minimum:
            return f"must be at least {minimum} characters"
        return None

    return validate


def digits() -> CharFilter:
    """Returns a filter accepting only ASCII digits."""
    return lambda ch: "0" <= ch <= "9"


def decimal() -> CharFilter:
    """Returns a filter accepting digits plus a sign and decimal point."""
    return lambda ch: ("0" <= ch <= "9") or ch in {".", "-"}


def alpha() -> CharFilter:
    """Returns a filter accepting only alphabetic characters."""
    return lambda ch: ch.isalpha()


def alnum() -> CharFilter:
    """Returns a filter accepting only alphanumeric characters."""
    return lambda ch: ch.isalnum()


def no_space() -> CharFilter:
    """Returns a filter rejecting whitespace."""
    return lambda ch: not ch.isspace()
