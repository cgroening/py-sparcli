"""
sparcli.input.textarea
======================

Defines :class:`Textarea`, a multi-line text input prompt.

The textarea drives a :class:`~sparcli.input.line_edit.LineEditor` in multi-line
mode: Enter inserts a newline, Ctrl-D submits the whole buffer and Esc cancels.
Arrows plus Home/End move the caret (Shift extends a selection), Up/Down move
between rows preserving the column, and the usual Ctrl editing keys apply. With
the editor enabled, Ctrl-G opens ``$EDITOR`` on a Markdown temp file and folds
the result back in. Each buffer line is rendered under the prompt, with a block
cursor on the caret's line that is dropped on the final frame.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.text import Line
from sparcli.core.theme import theme
from sparcli.input.editor import edit_or_none
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
)
from sparcli.input.field import field_line
from sparcli.input.line_edit import (
    CTRL_ACTIONS,
    LineEditor,
    apply_caret_key,
)
from sparcli.input.prompt import Flow, run_on_terminal, run_prompt

if TYPE_CHECKING:
    from sparcli.input.outcome import Outcome

logger = logging.getLogger(__name__)

# Flow specialized for this prompt, so control constructors bind their type.
_StrFlow = Flow[str]

# Temp-file extension used when editing the buffer in an external editor.
_EDITOR_SUFFIX = ".md"
# Ctrl-letter that submits the buffer.
_SUBMIT_KEY = "d"
# Ctrl-letter that opens the external editor.
_EDITOR_KEY = "g"


class Textarea:
    """
    A multi-line text input prompt.

    Attributes
    ----------
    prompt : str
        The label shown above the buffer.

    Examples
    --------
    >>> area = Textarea("Notes").initial("hello")
    >>> area.frame().height()
    2
    """

    __slots__ = ("_editor_command", "_editor_enabled", "_initial", "_prompt")

    def __init__(
        self,
        prompt: str,
        *,
        initial: str = "",
        editor_enabled: bool = False,
        editor_command: str | None = None,
    ) -> None:
        self._prompt = prompt
        self._initial = initial
        self._editor_enabled = editor_enabled or editor_command is not None
        self._editor_command = editor_command

    def initial(self, value: str) -> Textarea:
        """Sets the initial multi-line value and returns ``self``."""
        self._initial = value
        return self

    def editor(self) -> Textarea:
        """Enables opening the buffer in ``$EDITOR`` with Ctrl-G."""
        self._editor_enabled = True
        return self

    def editor_command(self, command: str) -> Textarea:
        """Sets the editor command (implies :meth:`editor`)."""
        self._editor_enabled = True
        self._editor_command = command
        return self

    def run(self) -> Outcome[str]:
        """
        Runs the prompt on the real terminal.

        Returns
        -------
        Outcome[str]
            The submitted text or a cancellation.

        Raises
        ------
        NoTerminalError
            If standard input or output is not an interactive terminal.
        """
        return run_on_terminal(self.run_with)

    def run_with(self, source: EventSource) -> Outcome[str]:
        """
        Runs the prompt against any event source (used for tests).

        Parameters
        ----------
        source : EventSource
            The source of input events driving the prompt.

        Returns
        -------
        Outcome[str]
            The prompt result.
        """
        editor = LineEditor(self._initial, multiline=True)
        return run_prompt(source, editor, self._render, self._handle)

    def frame(self) -> Rendered:
        """Renders the prompt's static frame without running it."""
        return self._render(LineEditor(self._initial, multiline=True), False)

    def _render(self, editor: LineEditor, final_frame: bool) -> Rendered:
        """Builds the frame, drawing the cursor on its line."""
        active = theme()
        cursor_line, cursor_col = editor.cursor_line_col()
        lines = [Line.styled(self._prompt, active.title)]
        for index, text in enumerate(editor.lines()):
            if index == cursor_line and not final_frame:
                lines.append(
                    field_line("", text, cursor_col, Style.new(), active)
                )
            else:
                lines.append(Line.raw(text))
        return Rendered(lines)

    def _handle(self, editor: LineEditor, event: InputEvent) -> Flow[str]:
        """Handles one event for the textarea."""
        if event.kind is EventKind.PASTE and event.text is not None:
            editor.insert_str(event.text)
            return _StrFlow.cont()
        if event.kind is not EventKind.KEY or event.key is None:
            return _StrFlow.cont()
        return self._handle_key(editor, event.key)

    def _handle_key(self, editor: LineEditor, key: KeyPress) -> Flow[str]:
        """Handles a single key press (delegating Ctrl keys)."""
        if key.ctrl:
            return self._handle_ctrl(editor, key)
        code = key.code
        if code == KeyCode.ESC:
            return _StrFlow.cancel()
        _apply_edit(editor, key)
        return _StrFlow.cont()

    def _handle_ctrl(self, editor: LineEditor, key: KeyPress) -> Flow[str]:
        """Handles Ctrl-modified keys (submit, editor and edit ops)."""
        code = key.code
        if code.kind is not KeyKind.CHAR or code.ch is None:
            return _StrFlow.cont()
        ch = code.ch
        if ch == _SUBMIT_KEY:
            return _StrFlow.submit(editor.value())
        if ch == _EDITOR_KEY and self._editor_enabled:
            return self._launch_editor(editor)
        operation = CTRL_ACTIONS.get(ch)
        if operation is not None:
            operation(editor)
        return _StrFlow.cont()

    def _launch_editor(self, editor: LineEditor) -> Flow[str]:
        """Opens the buffer in an external editor, then refreshes."""
        text = edit_or_none(
            self._editor_command, editor.value(), _EDITOR_SUFFIX
        )
        if text is not None:
            editor.set_value(text.rstrip("\n"))
        return _StrFlow.refresh()


def _apply_edit(editor: LineEditor, key: KeyPress) -> None:
    """Applies a non-Ctrl editing or movement key to the editor."""
    code = key.code
    if code == KeyCode.ENTER:
        editor.insert_newline()
    elif code == KeyCode.UP:
        editor.move_up(select=key.shift)
    elif code == KeyCode.DOWN:
        editor.move_down(select=key.shift)
    elif apply_caret_key(editor, key, select=key.shift):
        return
    elif code.kind is KeyKind.CHAR and code.ch is not None:
        editor.insert_char(code.ch)
