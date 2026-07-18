"""
sparcli.input.select
====================

Defines :class:`Select`, the single- and multi-selection list prompt.

A :class:`Select` shows a scrollable list of options and lets the user move a
cursor, optionally toggle checkboxes (multi-select) and submit. It follows the
shared prompt pattern: a kwargs constructor plus fluent builders, a
:meth:`Select.run` guarded on an interactive terminal, and a
:meth:`Select.run_with` that drives any
:class:`~sparcli.input.event.EventSource` for headless tests. Navigation
cycles by default and the visible window scrolls to keep the cursor on screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line, Span
from sparcli.core.theme import theme
from sparcli.input.event import EventKind, KeyCode
from sparcli.input.outcome import Outcome
from sparcli.input.prompt import Flow, run_on_terminal, run_prompt
from sparcli.input.selection import (
    SelectionCursor,
    checked_indices,
    first_index,
)
from sparcli.input.shortcut import (
    Shortcut,
    find,
    help_overlay,
    hint_line,
    opens_help,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sparcli.core.theme import Theme
    from sparcli.input.event import EventSource, InputEvent, KeyPress

# Default number of visible rows.
DEFAULT_VISIBLE = 10

# The prompt collects indices, so every flow it produces carries this type.
_Flow = Flow[list[int]]

# Character keys handled specially by the prompt.
_VIM_UP = KeyCode.char("k")
_VIM_DOWN = KeyCode.char("j")
_SPACE = KeyCode.char(" ")


class _State:
    """The mutable state of a running select prompt."""

    __slots__ = ("checked", "cursor", "help", "offset")

    def __init__(self, cursor: int, checked: list[bool], offset: int) -> None:
        self.cursor = cursor
        self.checked = checked
        self.offset = offset
        self.help = False


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
        "_cursor",
        "_initial_checked",
        "_initial_cursor",
        "_multi",
        "_options",
        "_prompt",
        "_shortcuts",
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
        self._cursor = SelectionCursor(max_visible, cycle)
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
        self._cursor.max_visible = max(rows, 1)
        return self

    def no_cycle(self) -> Select:
        """Disables wrap-around navigation and returns ``self``."""
        self._cursor.cycle = False
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
        return first_index(self._run_collect())

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
        return run_on_terminal(self.run_with)

    def _initial_state(self) -> _State:
        """Builds the starting state from the initial cursor and checks."""
        length = len(self._options)
        cursor = min(self._initial_cursor, max(length - 1, 0))
        checked = [False] * length
        for index in self._initial_checked:
            if 0 <= index < length:
                checked[index] = True
        offset = self._cursor.opening_offset(cursor)
        return _State(cursor=cursor, checked=checked, offset=offset)

    def _render(self, state: _State, _final: bool) -> Rendered:
        """Builds the frame with the visible window of options."""
        active = theme()
        if state.help:
            return Rendered(help_overlay(self._shortcuts))
        lines = [Line.styled(self._prompt, active.title)]
        end = min(state.offset + self._cursor.max_visible, len(self._options))
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
        if state.help:
            state.help = False
            return _Flow.cont()
        if opens_help(key, self._shortcuts):
            state.help = True
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
        length = len(self._options)
        page = self._cursor.max_visible
        if code in (KeyCode.UP, _VIM_UP):
            self._cursor.move(state, -1, length)
        elif code in (KeyCode.DOWN, _VIM_DOWN):
            self._cursor.move(state, 1, length)
        elif code == KeyCode.HOME:
            self._cursor.set(state, 0)
        elif code == KeyCode.END:
            self._cursor.set(state, length - 1)
        elif code == KeyCode.PAGE_UP:
            self._cursor.move(state, -page, length)
        elif code == KeyCode.PAGE_DOWN:
            self._cursor.move(state, page, length)
        elif code == _SPACE and self._multi:
            state.checked[state.cursor] = not state.checked[state.cursor]

    def _collect(self, state: _State) -> list[int]:
        """Returns the result indices for the current state."""
        if self._multi:
            return checked_indices(state.checked)
        return [state.cursor]
