"""
sparcli.input.selection
=======================

Defines the scrolling cursor shared by the list prompts.

:class:`Select` and :class:`FuzzySelect` navigate the same way: a cursor moves
through a list, wraps around or clamps at the ends, and drags a scroll offset
along so the cursor stays inside the visible window. :class:`SelectionCursor`
owns that arithmetic once; both prompts hold one by composition instead of
copying the same handful of methods.

:func:`first_index` reduces a collected multi-select outcome to the single
index the ``run()`` entry points return.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from sparcli.input.outcome import Outcome

if TYPE_CHECKING:
    from collections.abc import Sequence


class Scrollable(Protocol):
    """A prompt state that carries a cursor and a scroll offset."""

    cursor: int
    offset: int


class SelectionCursor:
    """
    Moves a cursor through a list and keeps it inside the visible window.

    Attributes
    ----------
    max_visible : int
        The number of rows on screen; the scroll offset follows the cursor
        so it never leaves that window.
    cycle : bool
        Whether movement wraps around at both ends instead of clamping.
    """

    __slots__ = ("cycle", "max_visible")

    def __init__(self, max_visible: int, cycle: bool = True) -> None:
        self.max_visible = max(max_visible, 1)
        self.cycle = cycle

    def move(self, state: Scrollable, delta: int, length: int) -> None:
        """
        Moves the cursor by ``delta``, wrapping or clamping per ``cycle``.

        Parameters
        ----------
        state : Scrollable
            The prompt state carrying ``cursor`` and ``offset``.
        delta : int
            How far to move; negative moves towards the top.
        length : int
            The number of rows currently navigable.
        """
        if length == 0:
            return
        target = state.cursor + delta
        if self.cycle:
            target %= length
        else:
            target = max(0, min(target, length - 1))
        self.set(state, target)

    def set(self, state: Scrollable, index: int) -> None:
        """
        Places the cursor on ``index`` and scrolls it into view.

        Parameters
        ----------
        state : Scrollable
            The prompt state carrying ``cursor`` and ``offset``.
        index : int
            The row to place the cursor on.
        """
        state.cursor = index
        if index < state.offset:
            state.offset = index
        elif index >= state.offset + self.max_visible:
            state.offset = index + 1 - self.max_visible

    def opening_offset(self, cursor: int) -> int:
        """
        Returns the scroll offset that shows ``cursor`` on the opening frame.

        Parameters
        ----------
        cursor : int
            The initially highlighted row.

        Returns
        -------
        int
            The offset the prompt starts scrolled to.
        """
        return max(cursor - (self.max_visible - 1), 0)


def checked_indices(checked: Sequence[bool]) -> list[int]:
    """
    Returns the positions that are checked, in order.

    Parameters
    ----------
    checked : Sequence[bool]
        One flag per row.

    Returns
    -------
    list[int]
        The indices whose flag is set.
    """
    return [index for index, flag in enumerate(checked) if flag]


def first_index(outcome: Outcome[list[int]]) -> Outcome[int]:
    """
    Reduces a collected outcome to its first index (single-select).

    Parameters
    ----------
    outcome : Outcome[list[int]]
        The outcome a multi-select loop produced.

    Returns
    -------
    Outcome[int]
        The first submitted index, or the cancellation/shortcut unchanged.
    """
    if outcome.is_shortcut:
        return Outcome.shortcut(outcome.shortcut_id or 0)
    if outcome.is_submitted and outcome.value:
        return Outcome.submitted(outcome.value[0])
    return Outcome.cancelled()
