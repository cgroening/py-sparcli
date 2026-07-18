"""
sparcli.input.prompt
====================

Defines the shared prompt driver: render a frame, read an event, repeat.

:func:`run_prompt` centralizes the event loop so each prompt supplies only a
render callback and an event handler. The handler returns a :class:`Flow`
telling the loop what to do next: keep going, submit a value, cancel, fire a
shortcut, or refresh after an external program drew over the screen. Drawing
goes through :class:`~sparcli.core.inplace.InPlace`, so the loop is a no-op for
non-interactive sources.

:func:`run_on_terminal` is the matching entry point for the public ``run()``
methods: it guards on an interactive terminal and wraps the loop in a
:class:`~sparcli.input.guard.TerminalGuard`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from sparcli.core.inplace import InPlace
from sparcli.core.terminal import is_input_tty
from sparcli.errors import NoTerminalError
from sparcli.input.event import EventSource, TerminalSource
from sparcli.input.guard import TerminalGuard
from sparcli.input.outcome import Outcome

if TYPE_CHECKING:
    from collections.abc import Callable

    from sparcli.core.render import Rendered
    from sparcli.input.event import InputEvent


class FlowKind(enum.Enum):
    """What a prompt's event handler decides after each event."""

    CONTINUE = enum.auto()
    SUBMIT = enum.auto()
    CANCEL = enum.auto()
    SHORTCUT = enum.auto()
    REFRESH = enum.auto()


@dataclass(frozen=True, slots=True, match_args=False)
class Flow[T]:
    """
    The next step a prompt loop takes after handling an event.

    Attributes
    ----------
    kind : FlowKind
        Which control-flow decision this represents.
    """

    kind: FlowKind
    _value: object = None
    _id: int | None = None

    __match_args__ = ("kind",)

    @classmethod
    def cont(cls) -> Flow[T]:
        """Returns a flow that keeps the prompt open and redraws."""
        return cls(FlowKind.CONTINUE)

    @classmethod
    def submit(cls, value: T) -> Flow[T]:
        """Returns a flow that finishes with a submitted value."""
        return cls(FlowKind.SUBMIT, value)

    @classmethod
    def cancel(cls) -> Flow[T]:
        """Returns a flow that finishes as cancelled."""
        return cls(FlowKind.CANCEL)

    @classmethod
    def shortcut(cls, shortcut_id: int) -> Flow[T]:
        """Returns a flow that finishes because a shortcut fired."""
        return cls(FlowKind.SHORTCUT, None, shortcut_id)

    @classmethod
    def refresh(cls) -> Flow[T]:
        """Returns a flow that keeps open but redraws from scratch."""
        return cls(FlowKind.REFRESH)

    @property
    def value(self) -> T:
        """Returns the submitted value; only valid for a submit flow."""
        return cast("T", self._value)

    @property
    def shortcut_id(self) -> int | None:
        """Returns the fired shortcut id, or ``None`` for non-shortcut flows."""
        return self._id


def run_prompt[S, T](
    source: EventSource,
    state: S,
    render: Callable[[S, bool], Rendered],
    handle: Callable[[S, InputEvent], Flow[T]],
) -> Outcome[T]:
    """
    Runs a prompt loop over ``source``, driving ``render`` and ``handle``.

    Parameters
    ----------
    source : EventSource
        Where events come from; its interactivity selects the draw engine.
    state : S
        The prompt state, mutated in place by ``handle``.
    render : Callable[[S, bool], Rendered]
        Builds the current frame. Its ``bool`` argument is ``True`` only for
        the final frame drawn after submission.
    handle : Callable[[S, InputEvent], Flow[T]]
        Consumes one event and returns the next :class:`Flow`.

    Returns
    -------
    Outcome[T]
        The submitted value, a cancellation, or a fired shortcut.
    """
    inplace = InPlace.create() if source.is_interactive() else InPlace.silent()
    while True:
        inplace.draw(render(state, False))
        flow = handle(state, source.next_event())
        if flow.kind is FlowKind.CONTINUE:
            continue
        if flow.kind is FlowKind.REFRESH:
            inplace.reset()
            continue
        if flow.kind is FlowKind.SUBMIT:
            inplace.draw(render(state, True))
            inplace.finish()
            return Outcome.submitted(flow.value)
        if flow.kind is FlowKind.SHORTCUT:
            inplace.finish()
            return Outcome.shortcut(flow.shortcut_id or 0)
        inplace.finish()
        return Outcome.cancelled()


def run_on_terminal[T](
    run_with: Callable[[EventSource], Outcome[T]],
) -> Outcome[T]:
    """
    Runs ``run_with`` against the real terminal, guarded and restored.

    Every public ``run()`` method funnels through here so the terminal check
    and the RAII guard exist exactly once.

    Parameters
    ----------
    run_with : Callable[[EventSource], Outcome[T]]
        The prompt's own ``run_with`` method.

    Returns
    -------
    Outcome[T]
        Whatever the prompt loop produced.

    Raises
    ------
    NoTerminalError
        If standard input or output is not an interactive terminal.
    """
    if not is_input_tty():
        raise NoTerminalError
    with TerminalGuard():
        return run_with(TerminalSource())
