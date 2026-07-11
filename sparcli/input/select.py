"""
sparcli.input.select
=====================

Defines :class:`Select`, the single- and multi-selection list prompt.

A :class:`Select` shows a scrollable list of options and lets the user move a
cursor, optionally toggle checkboxes (multi-select) and submit. It follows the
shared prompt pattern: a kwargs constructor plus fluent builders, a
:meth:`Select.run` guarded on an interactive terminal, and a
:meth:`Select.run_with` that drives any :class:`~sparcli.input.event.EventSource`
for headless tests. Navigation cycles by default and the visible window scrolls
to keep the cursor on screen.
"""

from __future__ import annotations

from collections.abc import Iterable

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.terminal import is_input_tty
from sparcli.core.text import Line, Span
from sparcli.core.theme import Theme, theme
from sparcli.errors import NoTerminalError
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyPress,
    TerminalSource,
)
from sparcli.input.guard import TerminalGuard
from sparcli.input.outcome import Outcome
from sparcli.input.prompt import Flow, run_prompt
from sparcli.input.shortcut import Shortcut, find, help_overlay, hint_line

# Default number of visible rows.
DEFAULT_VISIBLE = 10

# The prompt collects indices, so every flow it produces carries this type.
_Flow = Flow[list[int]]

# Character keys handled specially by the prompt.
_VIM_UP = KeyCode.char("k")
_VIM_DOWN = KeyCode.char("j")
_SPACE = KeyCode.char(" ")
_HELP = KeyCode.char("?")


class _State:
    """The mutable state of a running select prompt."""

    __slots__ = ("cursor", "checked", "offset", "show_help")

    def __init__(self, cursor: int, checked: list[bool], offset: int) -> None:
        self.cursor = cursor
        self.checked = checked
        self.offset = offset
        self.show_help = False


class Select:
    """
    A scrollable selection list, single- or multi-select.

    Attributes
    ----------
    prompt : str
        The label shown above the list.
    options : Iterable[str]
        The selectable rows.
    multi : bool
        Whether checkboxes and multi-selection are enabled.
    max_visible : int
        The maximum number of rows shown at once.
    cycle : bool
        Whether cursor navigation wraps around at the ends.
    shortcuts : Iterable[Shortcut]
        Custom shortcuts shown in the footer and the ``?`` help overlay.
    initial_cursor : int
        The row highlighted when the prompt opens.
    initial_checked : Iterable[int]
        The rows checked when a multi-select prompt opens.
    """

    __slots__ = (
        "_prompt",
        "_options",
        "_multi",
        "_max_visible",
        "_cycle",
        "_shortcuts",
        "_initial_cursor",
        "_initial_checked",
    )

    def __init__(
        self,
        prompt: str,
        *,
        options: Iterable[str] = (),
        multi: bool = False,
        max_visible: int = DEFAULT_VISIBLE,
        cycle: bool = True,
        shortcuts: Iterable[Shortcut] = (),
        initial_cursor: int = 0,
        initial_checked: Iterable[int] = (),
    ) -> None:
        self._prompt = prompt
        self._options = list(options)
        self._multi = multi
        self._max_visible = max(max_visible, 1)
        self._cycle = cycle
        self._shortcuts = list(shortcuts)
        self._initial_cursor = initial_cursor
        self._initial_checked = list(initial_checked)

    def options(self, options: Iterable[str]) -> Select:
        """Sets the selectable rows and returns ``self``."""
        self._options = list(options)
        return self

    def multi(self) -> Select:
        """Enables multi-selection with checkboxes and returns ``self``."""
        self._multi = True
        return self

    def max_visible(self, rows: int) -> Select:
        """Sets the maximum number of visible rows and returns ``self``."""
        self._max_visible = max(rows, 1)
        return self

    def no_cycle(self) -> Select:
        """Disables wrap-around navigation and returns ``self``."""
        self._cycle = False
        return self

    def cursor(self, index: int) -> Select:
        """Sets the initially highlighted row and returns ``self``."""
        self._initial_cursor = index
        return self

    def checked(self, indices: Iterable[int]) -> Select:
        """Sets the initially checked rows and returns ``self``."""
        self._initial_checked = list(indices)
        return self

    def shortcuts(self, shortcuts: Iterable[Shortcut]) -> Select:
        """Registers custom shortcuts and returns ``self``."""
        self._shortcuts = list(shortcuts)
        return self

    def run(self) -> Outcome[int]:
        """
        Runs a single-select prompt and returns the chosen index.

        Returns
        -------
        Outcome[int]
            The submitted index, a cancellation, or a fired shortcut.

        Raises
        ------
        NoTerminalError
            If standard input or output is not an interactive terminal.
        """
        return _first_index(self._run_collect())

    def run_multi(self) -> Outcome[list[int]]:
        """
        Runs a multi-select prompt and returns all checked indices.

        Returns
        -------
        Outcome[list[int]]
            The submitted indices, a cancellation, or a fired shortcut.

        Raises
        ------
        NoTerminalError
            If standard input or output is not an interactive terminal.
        """
        return self._run_collect()

    def run_with(self, source: EventSource) -> Outcome[list[int]]:
        """
        Runs the prompt against ``source`` and returns the checked indices.

        Parameters
        ----------
        source : EventSource
            The event source driving the prompt (a fake in tests).

        Returns
        -------
        Outcome[list[int]]
            The submitted indices, a cancellation, or a fired shortcut.
        """
        if not self._options:
            empty: list[int] = []
            return Outcome.submitted(empty)
        state = self._initial_state()
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the opening frame without running the prompt."""
        return self._render(self._initial_state(), False)

    def _run_collect(self) -> Outcome[list[int]]:
        """Sets up the terminal and runs the prompt loop."""
        if not is_input_tty():
            raise NoTerminalError
        with TerminalGuard():
            return self.run_with(TerminalSource())

    def _initial_state(self) -> _State:
        """Builds the starting state from the initial cursor and checks."""
        length = len(self._options)
        cursor = min(self._initial_cursor, max(length - 1, 0))
        checked = [False] * length
        for index in self._initial_checked:
            if 0 <= index < length:
                checked[index] = True
        offset = max(cursor - (self._max_visible - 1), 0)
        return _State(cursor=cursor, checked=checked, offset=offset)

    def _render(self, state: _State, _final: bool) -> Rendered:
        """Builds the frame with the visible window of options."""
        active = theme()
        if state.show_help:
            return Rendered(help_overlay(self._shortcuts))
        lines = [Line.styled(self._prompt, active.title)]
        end = min(state.offset + self._max_visible, len(self._options))
        for index in range(state.offset, end):
            lines.append(self._option_line(state, index, active))
        if self._shortcuts:
            lines.append(hint_line(self._shortcuts))
        return Rendered(lines)

    def _option_line(self, state: _State, index: int, active: Theme) -> Line:
        """Renders one option row."""
        is_cursor = index == state.cursor
        marker = active.cursor_marker() if is_cursor else active.marker()
        spans = [Span.styled(marker, active.selection)]
        if self._multi:
            checkbox = (
                active.checkbox_on()
                if state.checked[index]
                else active.checkbox_off()
            )
            spans.append(Span.raw(checkbox))
        style = active.selection if is_cursor else Style.new()
        spans.append(Span.styled(self._options[index], style))
        return Line(spans)

    def _handle(self, state: _State, event: InputEvent) -> _Flow:
        """Handles one input event."""
        if event.kind is not EventKind.KEY or event.key is None:
            return _Flow.cont()
        return self._handle_key(state, event.key)

    def _handle_key(self, state: _State, key: KeyPress) -> _Flow:
        """Handles a single key press."""
        if state.show_help:
            state.show_help = False
            return _Flow.cont()
        if key.code == _HELP and self._shortcuts:
            state.show_help = True
            return _Flow.cont()
        shortcut_id = find(key, self._shortcuts)
        if shortcut_id is not None:
            return _Flow.shortcut(shortcut_id)
        if key.code == KeyCode.ESC:
            return _Flow.cancel()
        if key.code == KeyCode.ENTER:
            return _Flow.submit(self._collect(state))
        self._navigate(state, key.code)
        return _Flow.cont()

    def _navigate(self, state: _State, code: KeyCode) -> None:
        """Applies a navigation or toggle key to the state."""
        if code in (KeyCode.UP, _VIM_UP):
            self._move_cursor(state, -1)
        elif code in (KeyCode.DOWN, _VIM_DOWN):
            self._move_cursor(state, 1)
        elif code == KeyCode.HOME:
            self._set_cursor(state, 0)
        elif code == KeyCode.END:
            self._set_cursor(state, len(self._options) - 1)
        elif code == KeyCode.PAGE_UP:
            self._move_cursor(state, -self._max_visible)
        elif code == KeyCode.PAGE_DOWN:
            self._move_cursor(state, self._max_visible)
        elif code == _SPACE and self._multi:
            state.checked[state.cursor] = not state.checked[state.cursor]

    def _collect(self, state: _State) -> list[int]:
        """Returns the result indices for the current state."""
        if self._multi:
            return [
                index
                for index in range(len(self._options))
                if state.checked[index]
            ]
        return [state.cursor]

    def _move_cursor(self, state: _State, delta: int) -> None:
        """Moves the cursor by ``delta``, cycling or clamping per config."""
        length = len(self._options)
        if length == 0:
            return
        target = state.cursor + delta
        if self._cycle:
            target %= length
        else:
            target = max(0, min(target, length - 1))
        self._set_cursor(state, target)

    def _set_cursor(self, state: _State, index: int) -> None:
        """Sets the cursor and scrolls so it stays visible."""
        state.cursor = index
        if index < state.offset:
            state.offset = index
        elif index >= state.offset + self._max_visible:
            state.offset = index + 1 - self._max_visible


def _first_index(outcome: Outcome[list[int]]) -> Outcome[int]:
    """Reduces a collected outcome to its first index (single-select)."""
    if outcome.is_shortcut:
        return Outcome.shortcut(outcome.shortcut_id or 0)
    if outcome.is_submitted and outcome.value:
        return Outcome.submitted(outcome.value[0])
    return Outcome.cancelled()
