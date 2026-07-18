"""
sparcli.input.completion
========================

Defines :class:`Completion`, the suggestion engine behind the text prompt.

Completing a typed value is its own concern: matching suggestions, offering the
best one as dim inline ghost text, or listing several in a navigable dropdown.
:class:`Completion` owns all of it, so :class:`~sparcli.input.text.TextInput`
only has to forward keys to it and render what it returns.

Matching is either by prefix (the default, which is what ghost text needs) or by
subsequence, selected through :class:`MatchMode`.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sparcli.core.text import Line, Span

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sparcli.core.theme import Theme

# Maximum number of dropdown rows shown at once.
MAX_DROPDOWN = 5


class MatchMode(enum.Enum):
    """How suggestions are matched against the typed value."""

    PREFIX = enum.auto()
    SUBSEQUENCE = enum.auto()


class Completion:
    """
    Matches suggestions against a typed value and renders the dropdown.

    Attributes
    ----------
    suggestions : list[str]
        The candidate completions, in declaration order.
    match_mode : MatchMode
        Whether candidates match by prefix or by subsequence.
    dropdown : bool
        Whether matches are shown as a navigable list instead of ghost text.
    """

    __slots__ = ("dropdown", "match_mode", "suggestions")

    def __init__(
        self,
        suggestions: Iterable[str] = (),
        *,
        match_mode: MatchMode = MatchMode.PREFIX,
        dropdown: bool = False,
    ) -> None:
        self.suggestions: list[str] = list(suggestions)
        self.match_mode = match_mode
        self.dropdown = dropdown

    def matches(self, value: str) -> list[int]:
        """
        Returns the suggestion indices matching ``value``, in declared order.

        Parameters
        ----------
        value : str
            The text typed so far; empty matches nothing.

        Returns
        -------
        list[int]
            Indices into :attr:`suggestions`.
        """
        if not value:
            return []
        needle = value.lower()
        return [
            index
            for index, suggestion in enumerate(self.suggestions)
            if _matches_suggestion(needle, suggestion, self.match_mode)
        ]

    def ghost(self, value: str) -> str | None:
        """
        Returns the inline ghost suffix completing ``value``, if any.

        Parameters
        ----------
        value : str
            The text typed so far.

        Returns
        -------
        str | None
            The remainder of the first suggestion that extends ``value``, or
            ``None`` when nothing completes it.
        """
        if not value:
            return None
        for suggestion in self.suggestions:
            if suggestion.startswith(value) and len(suggestion) > len(value):
                return suggestion[len(value) :]
        return None

    def rows(
        self, value: str, highlighted: int | None, active: Theme
    ) -> list[Line]:
        """
        Renders the dropdown rows for the matches of ``value``.

        Parameters
        ----------
        value : str
            The text typed so far.
        highlighted : int | None
            The highlighted row, or ``None`` when nothing is highlighted.
        active : Theme
            The theme supplying markers and styles.

        Returns
        -------
        list[Line]
            One line per visible match, capped at :data:`MAX_DROPDOWN`.
        """
        lines: list[Line] = []
        for row, index in enumerate(self.matches(value)[:MAX_DROPDOWN]):
            is_active = highlighted == row
            marker = active.cursor_marker() if is_active else active.marker()
            style = active.selection if is_active else active.secondary
            lines.append(
                Line(
                    [
                        Span.styled(marker, active.selection),
                        Span.styled(self.suggestions[index], style),
                    ]
                )
            )
        return lines

    def move(
        self, value: str, highlighted: int | None, delta: int
    ) -> int | None:
        """
        Returns the highlighted row after moving by ``delta``, cycling.

        Parameters
        ----------
        value : str
            The text typed so far, which determines how many rows exist.
        highlighted : int | None
            The currently highlighted row.
        delta : int
            How far to move; negative moves up.

        Returns
        -------
        int | None
            The new highlighted row, or ``None`` when there is nothing to
            highlight.
        """
        count = min(len(self.matches(value)), MAX_DROPDOWN)
        if count == 0:
            return None
        if highlighted is None:
            return 0 if delta > 0 else count - 1
        return (highlighted + delta) % count

    def accept(self, value: str, highlighted: int | None) -> str | None:
        """
        Returns the completed value, or ``None`` when nothing completes.

        In dropdown mode the highlighted row wins (falling back to the first
        match); otherwise the ghost suffix is appended.

        Parameters
        ----------
        value : str
            The text typed so far.
        highlighted : int | None
            The highlighted dropdown row, if any.

        Returns
        -------
        str | None
            The new full value, or ``None`` to leave the value untouched.
        """
        if not self.dropdown:
            ghost = self.ghost(value)
            return f"{value}{ghost}" if ghost is not None else None
        matches = self.matches(value)
        row = highlighted if highlighted is not None else 0
        if row < len(matches):
            return self.suggestions[matches[row]]
        return None


def _matches_suggestion(needle: str, suggestion: str, mode: MatchMode) -> bool:
    """Returns whether ``suggestion`` matches the lowercase ``needle``."""
    hay = suggestion.lower()
    if mode is MatchMode.PREFIX:
        return hay.startswith(needle)
    return _is_subsequence(needle, hay)


def _is_subsequence(needle: str, hay: str) -> bool:
    """Returns whether all chars of ``needle`` appear in ``hay`` in order."""
    chars = iter(hay)
    return all(target in chars for target in needle)
