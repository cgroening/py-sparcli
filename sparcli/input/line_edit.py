"""
sparcli.input.line_edit
======================

Defines :class:`LineEditor`, the shared text-editing core for input widgets.

This is the single source of truth for caret movement, selection and edit
operations behind both single- and multi-line prompts. Widgets own the control
keys (Enter, Esc, ...); the editor only edits. The clipboard is in-process (no
system dependency); the terminal's bracketed paste still delivers external text
through :meth:`LineEditor.insert_str`.
"""

from __future__ import annotations


class LineEditor:
    """A caret-and-selection text editor over a character buffer."""

    __slots__ = ("_chars", "_cursor", "_anchor", "_clipboard", "_multiline")

    def __init__(self, initial: str = "", *, multiline: bool = False) -> None:
        self._chars: list[str] = list(initial)
        self._cursor: int = len(self._chars)
        self._anchor: int | None = None
        self._clipboard: str = ""
        self._multiline: bool = multiline

    def value(self) -> str:
        """Returns the current text."""
        return "".join(self._chars)

    def set_value(self, value: str) -> None:
        """Replaces the entire buffer and moves the caret to the end."""
        self._chars = list(value)
        self._cursor = len(self._chars)
        self._anchor = None

    def __len__(self) -> int:
        """Returns the number of characters."""
        return len(self._chars)

    @property
    def cursor(self) -> int:
        """Returns the caret position as a character index."""
        return self._cursor

    def lines(self) -> list[str]:
        """Returns the display lines (split on newlines)."""
        return self.value().split("\n")

    def cursor_line_col(self) -> tuple[int, int]:
        """Returns the caret's ``(line, column)`` in characters."""
        line = 0
        col = 0
        for ch in self._chars[: self._cursor]:
            if ch == "\n":
                line += 1
                col = 0
            else:
                col += 1
        return (line, col)

    def selection_range(self) -> tuple[int, int] | None:
        """Returns the selection range as ``(start, end)`` if any."""
        anchor = self._anchor
        if anchor is None or anchor == self._cursor:
            return None
        return (min(anchor, self._cursor), max(anchor, self._cursor))

    def insert_char(self, ch: str) -> None:
        """Inserts a character, replacing any selection."""
        self._delete_selection()
        self._chars.insert(self._cursor, ch)
        self._cursor += 1

    def insert_str(self, text: str) -> None:
        """
        Inserts a string (e.g. a paste), replacing any selection.

        In single-line mode newlines are converted to spaces.
        """
        self._delete_selection()
        for ch in text:
            char = " " if not self._multiline and ch == "\n" else ch
            self._chars.insert(self._cursor, char)
            self._cursor += 1

    def insert_newline(self) -> None:
        """Inserts a newline (multi-line only; ignored otherwise)."""
        if self._multiline:
            self.insert_char("\n")

    def backspace(self) -> None:
        """Deletes the character before the caret, or the selection."""
        if self._delete_selection():
            return
        if self._cursor > 0:
            self._cursor -= 1
            del self._chars[self._cursor]

    def delete(self) -> None:
        """Deletes the character at the caret, or the selection."""
        if self._delete_selection():
            return
        if self._cursor < len(self._chars):
            del self._chars[self._cursor]

    def move_left(self, *, select: bool) -> None:
        """Moves the caret left by one character."""
        self._update_anchor(select=select)
        if self._cursor > 0:
            self._cursor -= 1

    def move_right(self, *, select: bool) -> None:
        """Moves the caret right by one character."""
        self._update_anchor(select=select)
        if self._cursor < len(self._chars):
            self._cursor += 1

    def move_home(self, *, select: bool) -> None:
        """Moves the caret to the start of the current line."""
        self._update_anchor(select=select)
        self._cursor = self._line_start(self._cursor)

    def move_end(self, *, select: bool) -> None:
        """Moves the caret to the end of the current line."""
        self._update_anchor(select=select)
        self._cursor = self._line_end(self._cursor)

    def move_up(self, *, select: bool) -> None:
        """Moves the caret up one line, preserving the column."""
        self._update_anchor(select=select)
        start = self._line_start(self._cursor)
        if start == 0:
            return
        col = self._cursor - start
        prev_start = self._line_start(start - 1)
        prev_end = start - 1
        self._cursor = min(prev_start + col, prev_end)

    def move_down(self, *, select: bool) -> None:
        """Moves the caret down one line, preserving the column."""
        self._update_anchor(select=select)
        end = self._line_end(self._cursor)
        if end >= len(self._chars):
            return
        col = self._cursor - self._line_start(self._cursor)
        next_start = end + 1
        next_end = self._line_end(next_start)
        self._cursor = min(next_start + col, next_end)

    def select_all(self) -> None:
        """Selects the entire buffer."""
        self._anchor = 0
        self._cursor = len(self._chars)

    def delete_word_back(self) -> None:
        """Deletes the previous whitespace-delimited word."""
        if self._delete_selection():
            return
        index = self._cursor
        while index > 0 and self._chars[index - 1].isspace():
            index -= 1
        while index > 0 and not self._chars[index - 1].isspace():
            index -= 1
        del self._chars[index : self._cursor]
        self._cursor = index

    def kill_to_line_start(self) -> None:
        """Deletes from the caret to the start of the current line."""
        start = self._line_start(self._cursor)
        del self._chars[start : self._cursor]
        self._cursor = start

    def kill_to_line_end(self) -> None:
        """Deletes from the caret to the end of the current line."""
        end = self._line_end(self._cursor)
        del self._chars[self._cursor : end]

    def copy(self) -> None:
        """Copies the selection to the in-process clipboard."""
        span = self.selection_range()
        if span is not None:
            start, end = span
            self._clipboard = "".join(self._chars[start:end])

    def cut(self) -> None:
        """Cuts the selection to the in-process clipboard."""
        self.copy()
        self._delete_selection()

    def paste(self) -> None:
        """Pastes the in-process clipboard at the caret."""
        self.insert_str(self._clipboard)

    def _update_anchor(self, *, select: bool) -> None:
        """Sets or clears the selection anchor before a movement."""
        if select:
            if self._anchor is None:
                self._anchor = self._cursor
        else:
            self._anchor = None

    def _delete_selection(self) -> bool:
        """Deletes the current selection; returns whether anything was removed."""
        span = self.selection_range()
        if span is None:
            self._anchor = None
            return False
        start, end = span
        del self._chars[start:end]
        self._cursor = start
        self._anchor = None
        return True

    def _line_start(self, index: int) -> int:
        """Returns the index of the start of the line containing ``index``."""
        for pos in range(index - 1, -1, -1):
            if self._chars[pos] == "\n":
                return pos + 1
        return 0

    def _line_end(self, index: int) -> int:
        """Returns the index of the end of the line containing ``index``."""
        for pos in range(index, len(self._chars)):
            if self._chars[pos] == "\n":
                return pos
        return len(self._chars)
