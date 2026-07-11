"""
sparcli.input.number
====================

Defines :class:`NumberInput`, a numeric prompt with an optional calculator.

The prompt edits a single line through :class:`~sparcli.input.line_edit.\
LineEditor`, accepts only characters that can form a number (or, in calculator
mode, a full arithmetic expression), and adjusts the value with the Up and Down
arrows. On submit it parses the field, clamps it to the configured range and
returns the value in an :class:`~sparcli.input.outcome.Outcome`.
"""

from __future__ import annotations

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.terminal import is_input_tty
from sparcli.core.theme import theme
from sparcli.errors import NoTerminalError
from sparcli.input.calc import CalcError, evaluate, parse_number
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
    TerminalSource,
)
from sparcli.input.field import error_line, field_line, value_line
from sparcli.input.guard import TerminalGuard
from sparcli.input.line_edit import LineEditor
from sparcli.input.outcome import Outcome
from sparcli.input.prompt import Flow, run_prompt

# Characters that may form a plain number.
_NUMERIC_CHARS = "0123456789.,-"
# Extra characters accepted only in calculator mode.
_CALC_CHARS = "+*/() "


class _State:
    """The mutable state of a running number prompt."""

    __slots__ = ("editor", "error")

    def __init__(self, editor: LineEditor) -> None:
        self.editor = editor
        self.error: str | None = None


class NumberInput:
    """A numeric input prompt with bounds, step and optional calculator mode."""

    __slots__ = (
        "_prompt",
        "_initial",
        "_minimum",
        "_maximum",
        "_step",
        "_decimals",
        "_calculator",
    )

    def __init__(
        self,
        prompt: str = "",
        *,
        initial: float = 0.0,
        minimum: float = float("-inf"),
        maximum: float = float("inf"),
        step: float = 1.0,
        decimals: int = 0,
        calculator: bool = False,
    ) -> None:
        self._prompt = prompt
        self._initial = initial
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._decimals = decimals
        self._calculator = calculator

    def initial(self, value: float) -> NumberInput:
        """Sets the initial value and returns ``self``."""
        self._initial = value
        return self

    def range(self, minimum: float, maximum: float) -> NumberInput:
        """Sets the inclusive ``[minimum, maximum]`` bounds and returns self."""
        self._minimum = minimum
        self._maximum = maximum
        return self

    def step(self, step: float) -> NumberInput:
        """Sets the step used by Up and Down and returns ``self``."""
        self._step = step
        return self

    def decimals(self, decimals: int) -> NumberInput:
        """Sets the number of decimal places shown and returns ``self``."""
        self._decimals = decimals
        return self

    def calculator(self) -> NumberInput:
        """Enables calculator expressions (``+ - * / ( )``); returns self."""
        self._calculator = True
        return self

    def run(self) -> Outcome[float]:
        """
        Runs the prompt on the real terminal.

        Returns
        -------
        Outcome[float]
            The clamped submitted value or a cancellation.

        Raises
        ------
        NoTerminalError
            If there is no interactive terminal.
        """
        if not is_input_tty():
            raise NoTerminalError()
        with TerminalGuard():
            return self.run_with(TerminalSource())

    def run_with(self, source: EventSource) -> Outcome[float]:
        """Runs the prompt against any event source (used for tests)."""
        state = _State(LineEditor(self._format(self._initial)))
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the prompt's static frame without running it."""
        state = _State(LineEditor(self._format(self._initial)))
        return self._render(state, False)

    def _render(self, state: _State, final: bool) -> Rendered:
        """Builds the prompt frame; ``final`` drops the cursor after submit."""
        active = theme()
        value = state.editor.value()
        if final:
            line = value_line(self._prompt, value, Style.new(), active)
            return Rendered([line])
        lines = [
            field_line(
                self._prompt, value, state.editor.cursor, Style.new(), active
            )
        ]
        if state.error is not None:
            lines.append(error_line(state.error, active))
        return Rendered(lines)

    def _handle(self, state: _State, event: InputEvent) -> Flow[float]:
        """Handles one input event."""
        if event.kind is not EventKind.KEY or event.key is None:
            return Flow[float].cont()
        return self._handle_key(state, event.key)

    def _handle_key(self, state: _State, key: KeyPress) -> Flow[float]:
        """Handles a single key press."""
        if key.is_ctrl("u"):
            state.editor.kill_to_line_start()
            return Flow[float].cont()
        code = key.code
        if code == KeyCode.ESC:
            return Flow[float].cancel()
        if code == KeyCode.ENTER:
            return self._submit(state)
        self._edit(state, code)
        return Flow[float].cont()

    def _edit(self, state: _State, code: KeyCode) -> None:
        """Applies a non-terminal editing or navigation key."""
        editor = state.editor
        if code == KeyCode.UP:
            self._adjust(state, self._step)
        elif code == KeyCode.DOWN:
            self._adjust(state, -self._step)
        elif code == KeyCode.LEFT:
            editor.move_left(select=False)
        elif code == KeyCode.RIGHT:
            editor.move_right(select=False)
        elif code == KeyCode.BACKSPACE:
            editor.backspace()
        elif code == KeyCode.DELETE:
            editor.delete()
        elif code.kind is KeyKind.CHAR and code.ch is not None:
            self._insert(state, code.ch)

    def _insert(self, state: _State, ch: str) -> None:
        """Inserts ``ch`` if it is a valid input character."""
        if not self._accepts(ch):
            return
        state.editor.insert_char(ch)
        state.error = None

    def _accepts(self, ch: str) -> bool:
        """Returns whether ``ch`` may be typed into the field."""
        numeric = ch in _NUMERIC_CHARS
        calc = ch in _CALC_CHARS
        return numeric or (self._calculator and calc)

    def _adjust(self, state: _State, delta: float) -> None:
        """Adjusts the current value by ``delta`` and reformats the field."""
        try:
            current = parse_number(state.editor.value())
        except CalcError:
            current = 0.0
        value = self._clamp(current + delta)
        state.editor.set_value(self._format(value))
        state.error = None

    def _submit(self, state: _State) -> Flow[float]:
        """Evaluates the field and submits the clamped value, or shows error."""
        text = state.editor.value()
        try:
            value = evaluate(text) if self._calculator else parse_number(text)
        except CalcError as error:
            state.error = str(error)
            return Flow[float].cont()
        return Flow[float].submit(self._clamp(value))

    def _clamp(self, value: float) -> float:
        """Clamps ``value`` to the configured range."""
        return max(self._minimum, min(value, self._maximum))

    def _format(self, value: float) -> str:
        """Formats ``value`` with the configured number of decimals."""
        return f"{value:.{self._decimals}f}"
