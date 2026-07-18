"""
sparcli.input.password
======================

Defines :class:`PasswordInput`, a masked single-line secret prompt.

The prompt edits one line through the shared :class:`~sparcli.input.line_edit.
LineEditor` but never shows the typed characters: each is drawn as a mask glyph
(``*`` by default), or the length is hidden entirely when the mask is empty. It
validates and filters input like :class:`~sparcli.input.text.TextInput` but
omits history, suggestions and selection, and returns an
:class:`~sparcli.input.outcome.Outcome` carrying the submitted secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.theme import theme
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
)
from sparcli.input.field import error_line, field_line, value_line
from sparcli.input.line_edit import CTRL_ACTIONS_MASKED, LineEditor
from sparcli.input.prompt import Flow, run_on_terminal, run_prompt

if TYPE_CHECKING:
    from sparcli.input.outcome import Outcome
    from sparcli.input.validate import CharFilter, Validator

# Default mask glyph shown for each typed character.
_DEFAULT_MASK = "*"


@dataclass(slots=True)
class _State:
    """Mutable state of a running password prompt."""

    editor: LineEditor
    error: str | None


class PasswordInput:
    """
    A masked password input prompt.

    Configure a prompt either through the keyword-only constructor options or
    the matching fluent setters (each mutates and returns ``self``, so calls
    chain), then run it with :meth:`run`. The typed value is displayed as
    repeated mask glyphs; an empty :meth:`mask` hides the length entirely.
    """

    __slots__ = (
        "_char_filter",
        "_initial",
        "_mask",
        "_max_chars",
        "_prompt",
        "_validator",
    )

    def __init__(
        self,
        prompt: str,
        *,
        initial: str = "",
        mask: str = _DEFAULT_MASK,
        max_chars: int = 0,
        validator: Validator | None = None,
        char_filter: CharFilter | None = None,
    ) -> None:
        self._prompt: str = prompt
        self._initial: str = initial
        self._mask: str = mask
        self._max_chars: int = max_chars
        self._validator: Validator | None = validator
        self._char_filter: CharFilter | None = char_filter

    def initial(self, value: str) -> PasswordInput:
        """Sets an initial value (mainly useful for previews)."""
        self._initial = value
        return self

    def mask(self, mask: str) -> PasswordInput:
        """Sets the mask glyph. An empty mask hides the length entirely."""
        self._mask = mask
        return self

    def max_chars(self, maximum: int) -> PasswordInput:
        """Limits the number of characters (0 = unlimited)."""
        self._max_chars = maximum
        return self

    def validate(self, validator: Validator) -> PasswordInput:
        """Sets a full-value validator and returns ``self``."""
        self._validator = validator
        return self

    def char_filter(self, char_filter: CharFilter) -> PasswordInput:
        """Sets a per-character filter and returns ``self``."""
        self._char_filter = char_filter
        return self

    def run(self) -> Outcome[str]:
        """
        Runs the prompt on the real terminal.

        Returns
        -------
        Outcome[str]
            The submitted secret or a cancellation.

        Raises
        ------
        NoTerminalError
            When there is no interactive terminal.
        """
        return run_on_terminal(self.run_with)

    def run_with(self, source: EventSource) -> Outcome[str]:
        """
        Runs the prompt against ``source`` and returns the outcome.

        Parameters
        ----------
        source : EventSource
            The event source driving the prompt (a fake in tests).

        Returns
        -------
        Outcome[str]
            The submitted value, a cancellation, or a fired shortcut.
        """
        state = _State(editor=LineEditor(self._initial), error=None)
        return run_prompt(source, state, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the static initial frame without running (for previews)."""
        state = _State(editor=LineEditor(self._initial), error=None)
        return self._render(state, False)

    def _render(self, state: _State, final: bool) -> Rendered:
        """Builds the prompt frame with the masked value."""
        active_theme = theme()
        display, cursor = self._masked(state)
        if final:
            line = value_line(self._prompt, display, Style.new(), active_theme)
            return Rendered([line])
        lines = [
            field_line(self._prompt, display, cursor, Style.new(), active_theme)
        ]
        if state.error is not None:
            lines.append(error_line(state.error, active_theme))
        return Rendered(lines)

    def _masked(self, state: _State) -> tuple[str, int]:
        """Returns the masked display string and cursor index."""
        if not self._mask:
            return ("", 0)
        glyph = self._mask[0]
        return (glyph * len(state.editor), state.editor.cursor)

    def _handle(self, state: _State, event: InputEvent) -> Flow[str]:
        """Handles one input event."""
        if event.kind is EventKind.PASTE and event.text is not None:
            for ch in event.text:
                self._type_char(state, ch)
            return Flow[str].cont()
        if event.kind is EventKind.KEY and event.key is not None:
            return self._handle_key(state, event.key)
        return Flow[str].cont()

    def _handle_key(self, state: _State, key: KeyPress) -> Flow[str]:
        """Handles a single key press."""
        if key.ctrl:
            self._handle_ctrl(state, key)
            return Flow[str].cont()
        code = key.code
        if code == KeyCode.ESC:
            return Flow[str].cancel()
        if code == KeyCode.ENTER:
            return self._submit(state)
        self._edit_key(state, code)
        return Flow[str].cont()

    def _edit_key(self, state: _State, code: KeyCode) -> None:
        """Applies a non-terminal editing or navigation key."""
        if code == KeyCode.LEFT:
            state.editor.move_left(select=False)
        elif code == KeyCode.RIGHT:
            state.editor.move_right(select=False)
        elif code == KeyCode.BACKSPACE:
            state.editor.backspace()
        elif code == KeyCode.DELETE:
            state.editor.delete()
        elif code.kind is KeyKind.CHAR and code.ch is not None:
            self._type_char(state, code.ch)

    def _handle_ctrl(self, state: _State, key: KeyPress) -> None:
        """Handles Ctrl-modified editing keys."""
        code = key.code
        if code.kind is not KeyKind.CHAR or code.ch is None:
            return
        action = CTRL_ACTIONS_MASKED.get(code.ch)
        if action is not None:
            action(state.editor)

    def _submit(self, state: _State) -> Flow[str]:
        """Validates and submits the current value."""
        value = state.editor.value()
        if self._validator is not None:
            message = self._validator(value)
            if message is not None:
                state.error = message
                return Flow[str].cont()
        return Flow[str].submit(value)

    def _type_char(self, state: _State, ch: str) -> None:
        """Types one character if it passes the filter and length limit."""
        if self._char_filter is not None and not self._char_filter(ch):
            return
        if self._max_chars > 0 and len(state.editor) >= self._max_chars:
            return
        state.editor.insert_char(ch)
        state.error = None
