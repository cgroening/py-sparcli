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
import sys
from collections.abc import Callable
from typing import Any

from sparcli.core.render import Rendered
from sparcli.core.style import Style
from sparcli.core.terminal import is_input_tty
from sparcli.core.text import Line
from sparcli.core.theme import theme
from sparcli.errors import NoTerminalError, SparcliError
from sparcli.input.editor import edit_text
from sparcli.input.event import (
    EventKind,
    EventSource,
    InputEvent,
    KeyCode,
    KeyKind,
    KeyPress,
    TerminalSource,
)
from sparcli.input.field import field_line
from sparcli.input.guard import TerminalGuard
from sparcli.input.line_edit import LineEditor
from sparcli.input.outcome import Outcome
from sparcli.input.prompt import Flow, run_prompt

logger = logging.getLogger(__name__)

# Flow specialized for this prompt, so control constructors bind their type.
_StrFlow = Flow[str]

# Temp-file extension used when editing the buffer in an external editor.
_EDITOR_SUFFIX = ".md"
# Ctrl-letter that submits the buffer.
_SUBMIT_KEY = "d"
# Ctrl-letter that opens the external editor.
_EDITOR_KEY = "g"

# Indices into a termios attribute list ``[iflag, oflag, cflag, lflag, ...]``.
_IFLAG = 0
_OFLAG = 1
_LFLAG = 3

# Ctrl-letter editing operations shared with the single-line text input.
_CTRL_OPS: dict[str, Callable[[LineEditor], None]] = {
    "a": LineEditor.select_all,
    "w": LineEditor.delete_word_back,
    "u": LineEditor.kill_to_line_start,
    "k": LineEditor.kill_to_line_end,
    "c": LineEditor.copy,
    "x": LineEditor.cut,
    "v": LineEditor.paste,
}


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

    __slots__ = ("_prompt", "_initial", "_editor_enabled", "_editor_command")

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
        if not is_input_tty():
            raise NoTerminalError()
        with TerminalGuard():
            return self.run_with(TerminalSource())

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
        operation = _CTRL_OPS.get(ch)
        if operation is not None:
            operation(editor)
        return _StrFlow.cont()

    def _launch_editor(self, editor: LineEditor) -> Flow[str]:
        """Opens the buffer in an external editor, then refreshes."""
        text = _edit_externally(self._editor_command, editor.value())
        if text is not None:
            editor.set_value(text.rstrip("\n"))
        return _StrFlow.refresh()


def _apply_edit(editor: LineEditor, key: KeyPress) -> None:
    """Applies a non-Ctrl editing or movement key to the editor."""
    code = key.code
    if code == KeyCode.ENTER:
        editor.insert_newline()
    elif code == KeyCode.LEFT:
        editor.move_left(select=key.shift)
    elif code == KeyCode.RIGHT:
        editor.move_right(select=key.shift)
    elif code == KeyCode.UP:
        editor.move_up(select=key.shift)
    elif code == KeyCode.DOWN:
        editor.move_down(select=key.shift)
    elif code == KeyCode.HOME:
        editor.move_home(select=key.shift)
    elif code == KeyCode.END:
        editor.move_end(select=key.shift)
    elif code == KeyCode.BACKSPACE:
        editor.backspace()
    elif code == KeyCode.DELETE:
        editor.delete()
    elif code.kind is KeyKind.CHAR and code.ch is not None:
        editor.insert_char(code.ch)


def _edit_externally(command: str | None, text: str) -> str | None:
    """Edits ``text`` externally with raw mode suspended; ``None`` on error."""
    saved = _suspend_raw()
    try:
        return edit_text(command, text, _EDITOR_SUFFIX)
    except SparcliError as error:
        logger.debug("external editor failed: %s", error)
        return None
    finally:
        _resume_raw(saved)


def _suspend_raw() -> tuple[int, list[Any]] | None:
    """Switches the terminal to cooked mode, returning the saved state."""
    if sys.platform == "win32":
        return None
    try:
        import termios  # noqa: PLC0415

        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        termios.tcsetattr(fd, termios.TCSADRAIN, _cooked_mode(saved))
    except (OSError, ValueError, ImportError):
        return None
    return (fd, saved)


def _cooked_mode(mode: list[Any]) -> list[Any]:
    """Returns a copy of ``mode`` with canonical input and echo enabled."""
    import termios  # noqa: PLC0415

    cooked = list(mode)
    cooked[_IFLAG] |= termios.ICRNL
    cooked[_OFLAG] |= termios.OPOST
    cooked[_LFLAG] |= termios.ICANON | termios.ECHO | termios.ISIG
    return cooked


def _resume_raw(saved: tuple[int, list[Any]] | None) -> None:
    """Restores the terminal state captured by :func:`_suspend_raw`."""
    if saved is None:
        return
    fd, mode = saved
    try:
        import termios  # noqa: PLC0415

        termios.tcsetattr(fd, termios.TCSADRAIN, mode)
    except (OSError, ValueError, ImportError):
        logger.debug("could not restore raw mode after the editor")
