"""
sparcli.input.outcome
=====================

Defines :class:`Outcome`, the result type returned by every interactive prompt.

A prompt never signals its result with an exception or ``None``: it returns an
:class:`Outcome` that is either a submitted value, a cancellation, or a fired
shortcut. The kind is carried by :class:`OutcomeKind`; the submitted value is
reached through :attr:`Outcome.value` (guarded) and the fired shortcut through
:attr:`Outcome.shortcut_id`. ``__match_args__`` exposes the kind for structural
pattern matching.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import cast

from sparcli.errors import SparcliError


class OutcomeKind(enum.Enum):
    """The three ways an interactive prompt can end."""

    SUBMITTED = enum.auto()
    CANCELLED = enum.auto()
    SHORTCUT = enum.auto()


@dataclass(frozen=True, slots=True, match_args=False)
class Outcome[T]:
    """
    The result of running an interactive prompt.

    Attributes
    ----------
    kind : OutcomeKind
        Which of the three terminal states the prompt reached.
    """

    kind: OutcomeKind
    _value: object = None
    _shortcut_id: int | None = None

    __match_args__ = ("kind",)

    @classmethod
    def submitted[U](cls, value: U) -> Outcome[U]:
        """Returns a submitted outcome carrying ``value``."""
        return Outcome[U](OutcomeKind.SUBMITTED, value)

    @classmethod
    def cancelled[U](cls) -> Outcome[U]:
        """Returns a cancelled outcome."""
        return Outcome[U](OutcomeKind.CANCELLED)

    @classmethod
    def shortcut[U](cls, shortcut_id: int) -> Outcome[U]:
        """Returns a shortcut outcome carrying the fired action id."""
        return Outcome[U](OutcomeKind.SHORTCUT, None, shortcut_id)

    @property
    def is_submitted(self) -> bool:
        """Returns whether the prompt ended with a submitted value."""
        return self.kind is OutcomeKind.SUBMITTED

    @property
    def is_cancelled(self) -> bool:
        """Returns whether the prompt was cancelled."""
        return self.kind is OutcomeKind.CANCELLED

    @property
    def is_shortcut(self) -> bool:
        """Returns whether the prompt ended on a registered shortcut."""
        return self.kind is OutcomeKind.SHORTCUT

    @property
    def value(self) -> T:
        """
        Returns the submitted value.

        Returns
        -------
        T
            The value the user submitted.

        Raises
        ------
        SparcliError
            If the outcome is not a submission.
        """
        if self.kind is not OutcomeKind.SUBMITTED:
            raise SparcliError("outcome carries no submitted value")
        return cast("T", self._value)

    @property
    def shortcut_id(self) -> int | None:
        """Returns the fired shortcut id, or ``None`` for other outcomes."""
        return self._shortcut_id

    def submitted_or(self, default: T) -> T:
        """Returns the submitted value, or ``default`` for other outcomes."""
        if self.kind is OutcomeKind.SUBMITTED:
            return cast("T", self._value)
        return default
